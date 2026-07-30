import logging
import time
from pathlib import Path
from typing import List, Tuple
import numpy as np
import cv2
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from torchvision.models import resnet34

# YOLOX imports
from yolox.exp import get_exp
from yolox.utils import postprocess
import torch.nn.functional as F
from core.domain import DetectedCard

logger = logging.getLogger(__name__)

class TableCardDetector:
    """YOLOX-based card detection with separate zones for player and board cards"""
    
    def __init__(self, weights_path: str, exp_file: str = None, device: str = "cpu"):
        """
        Args:
            weights_path: Path to .pth checkpoint file
            exp_file: Path to experiment config file (optional, will use default YOLOX-S if not provided)
            device: 'cpu' or 'cuda'
        """
        self.device = device
        self.weights_path = weights_path
        self.use_half = (device == "cuda")
        logger.info(f"Loading YOLOX card detector from {weights_path}")

        if not Path(weights_path).exists():
            raise FileNotFoundError(f"Model weights not found: {weights_path}")

        # Load experiment config
        if exp_file and Path(exp_file).exists():
            self.exp = get_exp(exp_file, None)
        else:
            # Default YOLOX-S configuration
            logger.info("Using default YOLOX-S configuration")
            self.exp = get_exp(None, "yolox-s")
            self.exp.num_classes = 2  # BoardCard and PlayerCard
        
        # Get model
        self.model = self.exp.get_model()
        self.model.to(device)
        self.model.eval()

        # Load weights

        logger.info("Loading checkpoint...")
        ckpt = torch.load(weights_path, map_location=device, weights_only=False)

        # Handle different checkpoint formats
        if isinstance(ckpt, dict) and "model" in ckpt:
            logger.info(f"📊 Checkpoint info: best_ap={ckpt.get('best_ap', 'N/A')}")
            model_weights = ckpt["model"]
            
            # Если model - это nn.Module объект, а не state_dict
            if hasattr(model_weights, 'state_dict'):
                model_weights = model_weights.state_dict()
            
            self.model.load_state_dict(model_weights)
            logger.info("✅ Model weights loaded successfully")
            
        elif isinstance(ckpt, dict) and "state_dict" in ckpt:
            self.model.load_state_dict(ckpt["state_dict"])
            logger.info("✅ Model weights loaded from state_dict")
            
        else:
            self.model.load_state_dict(ckpt)
            logger.info("✅ Model weights loaded directly")

        # Enable half precision for GPU
        if self.use_half:
            try:
                self.model = self.model.half()
                logger.info("✅ FP16 half-precision enabled for YOLOX")
            except Exception as e:
                logger.warning(f"Could not enable FP16: {e}")
                self.use_half = False

        # Enable torch.compile for PyTorch 2.0+ (GPU only)
        if hasattr(torch, 'compile') and device == "cuda":
            try:
                self.model = torch.compile(
                    self.model,
                    mode="reduce-overhead",
                    fullgraph=True
                )
                logger.info("✅ YOLOX optimized with torch.compile")
            except Exception as e:
                logger.warning(f"torch.compile failed for YOLOX: {e}")

        # Class names (based on your training config)
        self.class_names = {0: "BoardCard", 1: "PlayerCard"}
        
        # Input size from experiment config
        self.input_size = self.exp.test_size  # (640, 640)
        
        logger.info("YOLOX card detector loaded successfully")
    
    def predict(self, frame: np.ndarray, confidence_threshold: float = 0.25) -> List[DetectedCard]:
        """Detect cards with separate optimization for player and board cards"""
        if frame is None or frame.size == 0:
            return []

        try:
            start_time = time.perf_counter()

            # Preprocess image
            img, ratio = self._preprocess(frame)
            
            # Inference
            with torch.no_grad():
                outputs = self.model(img)

                logger.info(f"🔍 Raw model output shape: {outputs.shape}")

                # ===== ЛОГИРОВАНИЕ RAW OUTPUT =====
                boxes = outputs[..., :4]
                objectness = outputs[..., 4:5]
                class_probs = outputs[..., 5:]

                logger.info(f"🔍 Raw output stats:")
                logger.info(f"   Objectness - min: {objectness.min().item():.4f}, max: {objectness.max().item():.4f}, mean: {objectness.mean().item():.4f}")
                logger.info(f"   Class probs - min: {class_probs.min().item():.4f}, max: {class_probs.max().item():.4f}, mean: {class_probs.mean().item():.4f}")
                # ==================================

                # ===== ПРАВИЛЬНАЯ ОБРАБОТКА С POSTPROCESS =====
                outputs = postprocess(
                    outputs,
                    num_classes=self.exp.num_classes,
                    conf_thre=confidence_threshold,
                    nms_thre=0.45  # Standard NMS threshold for YOLOX
                )

                # Check if any detections found
                if outputs[0] is None:
                    logger.info(f"🔍 No predictions above threshold {confidence_threshold}")
                    return []

                predictions = outputs[0]  # [N, 7] = [x1, y1, x2, y2, obj_conf, class_conf, class_id]
                logger.info(f"🔍 Found {len(predictions)} detections after NMS")
                logger.info(f"🔍 Confidence scores (obj*cls):")
                logger.info(f"   Min: {(predictions[:, 4] * predictions[:, 5]).min().item():.4f}")
                logger.info(f"   Max: {(predictions[:, 4] * predictions[:, 5]).max().item():.4f}")
                logger.info(f"   Mean: {(predictions[:, 4] * predictions[:, 5]).mean().item():.4f}")
                # ============================================

            inference_time = (time.perf_counter() - start_time) * 1000
            logger.debug(f"⚡ YOLOX inference: {inference_time:.2f}ms")

            all_detections = []
            frame_height, frame_width = frame.shape[:2]

            # Process detections
            # postprocess() returns: [x1, y1, x2, y2, obj_conf, class_conf, class_id]
            for i in range(len(predictions)):
                pred = predictions[i].cpu().numpy()
                x1, y1, x2, y2, obj_conf, class_conf, cls_id = pred

                # Calculate final score (objectness * class_confidence)
                score = float(obj_conf * class_conf)
                cls_id = int(cls_id)

                # Scale bbox back to original image size
                x1 = int(x1 / ratio)
                y1 = int(y1 / ratio)
                x2 = int(x2 / ratio)
                y2 = int(y2 / ratio)

                # Validation checks
                if x2 <= x1 or y2 <= y1:
                    continue
                if (x2 - x1) < 20 or (y2 - y1) < 30:
                    continue
                if x1 < 0 or y1 < 0 or x2 >= frame_width or y2 >= frame_height:
                    x1 = max(0, x1)
                    y1 = max(0, y1)
                    x2 = min(frame_width - 1, x2)
                    y2 = min(frame_height - 1, y2)

                # Map class ID to kind
                kind_raw = self.class_names.get(cls_id, "unknown")
                kind = self._map_class_name(kind_raw)

                if kind == "unknown":
                    continue

                detection = DetectedCard(
                    bbox=(x1, y1, x2, y2),
                    kind=kind,
                    score=score
                )
                all_detections.append(detection)

            optimized_detections = self._optimize_card_detections(
                all_detections, frame_height, frame_width
            )

            logger.info(f"Detected {len(optimized_detections)} cards after optimization")
            return optimized_detections

        except Exception as e:
            logger.error(f"Detection error: {e}", exc_info=True)
            return []

    def _preprocess(self, img: np.ndarray) -> Tuple[torch.Tensor, float]:
        """Preprocess image for YOLOX (standard mode - NO normalization)"""
        # Get input size
        input_size = self.input_size

        # Calculate ratio
        img_h, img_w = img.shape[:2]
        ratio = min(input_size[0] / img_h, input_size[1] / img_w)

        # Resize image (keep as uint8)
        new_h, new_w = int(img_h * ratio), int(img_w * ratio)
        resized_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR).astype(np.uint8)

        # Create padded image (keep in [0, 255] range!)
        padded_img = np.ones((input_size[0], input_size[1], 3), dtype=np.uint8) * 114
        padded_img[:new_h, :new_w] = resized_img

        # HWC → CHW (NO BGR→RGB conversion! YOLOX expects BGR)
        padded_img = padded_img.transpose((2, 0, 1))
        padded_img = np.ascontiguousarray(padded_img, dtype=np.float32)

        # Convert to tensor (NO division by 255! Data stays in [0, 255])
        tensor = torch.from_numpy(padded_img).unsqueeze(0)
        tensor = tensor.to(self.device)

        if self.use_half:
            tensor = tensor.half()

        return tensor, ratio
    
    def _optimize_card_detections(self, detections: List[DetectedCard], 
                                frame_height: int, frame_width: int) -> List[DetectedCard]:
        # ===== ДОБАВЬ ДЕБАГ =====
        logger.info(f"🔍 Optimization input: {len(detections)} detections")
        for i, det in enumerate(detections):
            x1, y1, x2, y2 = det.bbox
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            logger.info(f"   Detection {i}: kind={det.kind}, score={det.score:.3f}, "
                    f"bbox=({x1},{y1},{x2},{y2}), center=({center_x},{center_y})")
        
        logger.info(f"   Frame size: {frame_width}x{frame_height}")
        # ======================
        
        player_cards = [d for d in detections if d.kind == "player"]
        board_cards = [d for d in detections if d.kind == "board"]
        
        logger.info(f"🔍 Split: {len(player_cards)} player, {len(board_cards)} board")
        
        optimized_player_cards = self._optimize_player_cards(player_cards, frame_height, frame_width)
        optimized_board_cards = self._optimize_board_cards(board_cards, frame_height, frame_width)
        
        logger.info(f"🔍 After optimization: {len(optimized_player_cards)} player, {len(optimized_board_cards)} board")
        
        return optimized_player_cards + optimized_board_cards
    
    def _optimize_player_cards(self, player_cards: List[DetectedCard], 
                             frame_height: int, frame_width: int) -> List[DetectedCard]:

        if not player_cards:
            return []
        
        bottom_zone_start = int(frame_height * 0.6)
        center_zone_left = int(frame_width * 0.2)
        center_zone_right = int(frame_width * 0.8)
        
        logger.info(f"🔍 Player card zones: bottom_y>{bottom_zone_start}, "
                f"center_x={center_zone_left}-{center_zone_right}")
        
        filtered_cards = []
        
        for card in player_cards:
            x1, y1, x2, y2 = card.bbox
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            in_bottom_zone = center_y >= bottom_zone_start
            in_center_zone = center_zone_left <= center_x <= center_zone_right
            not_too_high = center_y >= int(frame_height * 0.4)
            
            logger.info(f"   Player card: center=({center_x},{center_y}), "
                    f"in_bottom={in_bottom_zone}, in_center={in_center_zone}, "
                    f"not_too_high={not_too_high}")
            
            if in_bottom_zone or (in_center_zone and not_too_high):
                filtered_cards.append(card)
            else:
                logger.info(f"      ❌ FILTERED OUT")
        
        if len(filtered_cards) > 2:
            filtered_cards = sorted(filtered_cards, key=lambda x: x.score, reverse=True)[:2]
        
        return filtered_cards

    def _optimize_board_cards(self, board_cards: List[DetectedCard], 
                            frame_height: int, frame_width: int) -> List[DetectedCard]:
        if not board_cards:
            return []
        
        center_zone_top = int(frame_height * 0.2)
        center_zone_bottom = int(frame_height * 0.7)
        center_zone_left = int(frame_width * 0.15)
        center_zone_right = int(frame_width * 0.85)
        
        logger.info(f"🔍 Board card zones: y={center_zone_top}-{center_zone_bottom}, "
                f"x={center_zone_left}-{center_zone_right}")
        
        filtered_cards = []
        
        for card in board_cards:
            x1, y1, x2, y2 = card.bbox
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
            
            in_vertical_zone = center_zone_top <= center_y <= center_zone_bottom
            in_horizontal_zone = center_zone_left <= center_x <= center_zone_right
            
            logger.info(f"   Board card: center=({center_x},{center_y}), "
                    f"in_vert={in_vertical_zone}, in_horiz={in_horizontal_zone}")
            
            if in_vertical_zone and in_horizontal_zone:
                filtered_cards.append(card)
            else:
                logger.info(f"      ❌ FILTERED OUT")
        
        if len(filtered_cards) > 5:
            filtered_cards = sorted(filtered_cards, key=lambda x: x.score, reverse=True)[:5]
        
        filtered_cards = sorted(filtered_cards, key=lambda x: (x.bbox[0] + x.bbox[2]) // 2)
        
        return filtered_cards
    
    
    def _map_class_name(self, raw_name: str) -> str:
        name_mapping = {
            "BoardCard": "board",
            "PlayerCard": "player", 
            "board_card": "board",
            "player_card": "player",
            "Board": "board",
            "Player": "player"
        }
        return name_mapping.get(raw_name, raw_name.lower())

class CardClassifierResNet:
    """ResNet-based card classification"""

    def __init__(self, weights_path: str, device: str = "cpu"):
        self.device = device
        self.weights_path = weights_path
        self.use_half = (device == "cuda")  # Enable FP16 only on GPU
        logger.info(f"Loading card classifier from {weights_path}")

        if not Path(weights_path).exists():
            raise FileNotFoundError(f"Model weights not found: {weights_path}")

        self._load_model()
        self._setup_transforms()
        logger.info("Card classifier loaded successfully")
    
    def _load_model(self):
        checkpoint = torch.load(self.weights_path, map_location=self.device, weights_only=False)
        
        try:
            from torchvision.models import ResNet34_Weights
            self.model = resnet34(weights=None)
        except ImportError:
            self.model = resnet34(pretrained=False)
        
        num_features = self.model.fc.in_features
        self.model.fc = nn.Sequential(
            nn.Dropout(0.5),
            nn.Linear(num_features, 52)
        )
        
        if isinstance(checkpoint, dict):
            if 'model_state_dict' in checkpoint:
                self.model.load_state_dict(checkpoint['model_state_dict'])
            elif 'state_dict' in checkpoint:
                self.model.load_state_dict(checkpoint['state_dict'])
            else:
                self.model.load_state_dict(checkpoint)
        else:
            self.model = checkpoint
        
        self.model.to(self.device)
        self.model.eval()

        # Enable half precision for GPU
        if self.use_half:
            try:
                self.model = self.model.half()
                logger.info("✅ FP16 half-precision enabled for ResNet")
            except Exception as e:
                logger.warning(f"Could not enable FP16 for ResNet: {e}")
                self.use_half = False

        # Enable torch.compile for PyTorch 2.0+ (GPU only)
        if hasattr(torch, 'compile') and self.device == "cuda":
            try:
                self.model = torch.compile(
                    self.model,
                    mode="reduce-overhead",  # Best for inference
                    fullgraph=True
                )
                logger.info("✅ ResNet optimized with torch.compile")
            except Exception as e:
                logger.warning(f"torch.compile failed for ResNet: {e}")

        self.class_names = [
            "ace of clubs", "ace of diamonds", "ace of hearts", "ace of spades",
            "eight of clubs", "eight of diamonds", "eight of hearts", "eight of spades",
            "five of clubs", "five of diamonds", "five of hearts", "five of spades",
            "four of clubs", "four of diamonds", "four of hearts", "four of spades",
            "jack of clubs", "jack of diamonds", "jack of hearts", "jack of spades",
            "king of clubs", "king of diamonds", "king of hearts", "king of spades",
            "nine of clubs", "nine of diamonds", "nine of hearts", "nine of spades",
            "queen of clubs", "queen of diamonds", "queen of hearts", "queen of spades",
            "seven of clubs", "seven of diamonds", "seven of hearts", "seven of spades",
            "six of clubs", "six of diamonds", "six of hearts", "six of spades",
            "ten of clubs", "ten of diamonds", "ten of hearts", "ten of spades",
            "three of clubs", "three of diamonds", "three of hearts", "three of spades",
            "two of clubs", "two of diamonds", "two of hearts", "two of spades"
        ]
    
    def _setup_transforms(self):
        """Setup optimized transforms using cv2 instead of PIL for speed"""
        # Only normalization is needed, resize/conversion done with cv2
        self.normalize = transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    
    def _preprocess_crop(self, crop: np.ndarray) -> torch.Tensor:
        """Optimized preprocessing using cv2 (2-3x faster than PIL)"""
        # Resize using cv2 (much faster than PIL)
        resized = cv2.resize(crop, (224, 224), interpolation=cv2.INTER_LINEAR)

        # Convert BGR to RGB
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Convert to tensor and normalize [0, 255] -> [0, 1]
        tensor = torch.from_numpy(rgb).float() / 255.0

        # Change from HWC to CHW format
        tensor = tensor.permute(2, 0, 1)

        # Apply normalization
        tensor = self.normalize(tensor)

        # Convert to half precision if enabled
        if self.use_half:
            tensor = tensor.half()

        return tensor

    def classify_crop(self, crop: np.ndarray) -> Tuple[str, float]:
        """Classify a single card crop (legacy method, prefer classify_batch for multiple cards)"""
        if crop is None or crop.size == 0:
            return "unknown", 0.0

        try:
            tensor = self._preprocess_crop(crop).unsqueeze(0).to(self.device)

            with torch.inference_mode():
                output = self.model(tensor)
                probs = F.softmax(output, dim=1)
                confidence, index = torch.max(probs, dim=1)

            class_idx = index.item()
            confidence_score = confidence.item()

            if 0 <= class_idx < len(self.class_names):
                raw_label = self.class_names[class_idx]
                card_label = self._map_class_to_card(raw_label)
                return card_label, confidence_score

            return "unknown", confidence_score

        except Exception as e:
            logger.error(f"Classification error: {e}")
            return "unknown", 0.0

    def classify_batch(self, crops: List[np.ndarray]) -> List[Tuple[str, float]]:
        """Classify multiple card crops in a single batch (5-7x faster than sequential)"""
        if not crops or len(crops) == 0:
            return []

        try:
            # Start timing
            start_time = time.perf_counter()

            # Filter out invalid crops and keep track of indices
            valid_crops = []
            valid_indices = []
            for i, crop in enumerate(crops):
                if crop is not None and crop.size > 0:
                    valid_crops.append(crop)
                    valid_indices.append(i)

            if not valid_crops:
                return [("unknown", 0.0)] * len(crops)

            # Preprocess all crops using optimized cv2 pipeline
            preprocess_start = time.perf_counter()
            batch_tensors = []
            for crop in valid_crops:
                tensor = self._preprocess_crop(crop)
                batch_tensors.append(tensor)

            preprocess_time = (time.perf_counter() - preprocess_start) * 1000

            # Stack into batch and move to device
            batch = torch.stack(batch_tensors).to(self.device)

            # Single forward pass for all crops
            inference_start = time.perf_counter()
            with torch.inference_mode():
                outputs = self.model(batch)
                probs = F.softmax(outputs, dim=1)
                confidences, indices = torch.max(probs, dim=1)

            inference_time = (time.perf_counter() - inference_start) * 1000
            total_time = (time.perf_counter() - start_time) * 1000

            logger.debug(f"⚡ ResNet batch ({len(valid_crops)} cards): "
                        f"preprocess={preprocess_time:.2f}ms, "
                        f"inference={inference_time:.2f}ms, "
                        f"total={total_time:.2f}ms")

            # Process results
            results = [("unknown", 0.0)] * len(crops)
            for i, valid_idx in enumerate(valid_indices):
                class_idx = indices[i].item()
                confidence_score = confidences[i].item()

                if 0 <= class_idx < len(self.class_names):
                    raw_label = self.class_names[class_idx]
                    card_label = self._map_class_to_card(raw_label)
                    results[valid_idx] = (card_label, confidence_score)
                else:
                    results[valid_idx] = ("unknown", confidence_score)

            return results

        except Exception as e:
            logger.error(f"Batch classification error: {e}")
            return [("unknown", 0.0)] * len(crops)
    
    def _map_class_to_card(self, raw_label: str) -> str:
        name_mapping = {
            "ace of clubs": "Ac", "ace of diamonds": "Ad", "ace of hearts": "Ah", "ace of spades": "As",
            "king of clubs": "Kc", "king of diamonds": "Kd", "king of hearts": "Kh", "king of spades": "Ks",
            "queen of clubs": "Qc", "queen of diamonds": "Qd", "queen of hearts": "Qh", "queen of spades": "Qs",
            "jack of clubs": "Jc", "jack of diamonds": "Jd", "jack of hearts": "Jh", "jack of spades": "Js",
            "ten of clubs": "Tc", "ten of diamonds": "Td", "ten of hearts": "Th", "ten of spades": "Ts",
            "nine of clubs": "9c", "nine of diamonds": "9d", "nine of hearts": "9h", "nine of spades": "9s",
            "eight of clubs": "8c", "eight of diamonds": "8d", "eight of hearts": "8h", "eight of spades": "8s",
            "seven of clubs": "7c", "seven of diamonds": "7d", "seven of hearts": "7h", "seven of spades": "7s",
            "six of clubs": "6c", "six of diamonds": "6d", "six of hearts": "6h", "six of spades": "6s",
            "five of clubs": "5c", "five of diamonds": "5d", "five of hearts": "5h", "five of spades": "5s",
            "four of clubs": "4c", "four of diamonds": "4d", "four of hearts": "4h", "four of spades": "4s",
            "three of clubs": "3c", "three of diamonds": "3d", "three of hearts": "3h", "three of spades": "3s",
            "two of clubs": "2c", "two of diamonds": "2d", "two of hearts": "2h", "two of spades": "2s"
        }
        
        return name_mapping.get(raw_label.lower(), raw_label)
