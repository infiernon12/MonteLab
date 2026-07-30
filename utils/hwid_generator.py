import hashlib
import platform
import subprocess
import uuid
import re
from typing import Optional
import base64

def _xor_decrypt(data: str) -> str:
    """XOR деобфускация соли"""
    try:
        decoded = base64.b64decode(data)
        key = b'\x9F\x2E\x3B\x77\xC8\x45\x1A\x6D'
        return ''.join(chr(b ^ key[i % len(key)]) for i, b in enumerate(decoded))
    except:
        return data

# Обфусцированная соль для HWID (защита от клонирования)
_SALT = '7l5QEqd3cV/wRQkcpSFxXK0dazKGDEkJrQ=='  # "qpkeo2k2ok2kmdk123PENISd2"

class HWIDGenerator:
    """Генератор устойчивого HWID на основе стабильных характеристик оборудования"""
    
    @staticmethod
    def get_machine_guid() -> str:
        """Получение уникального Machine GUID (Windows) или аналога"""
        try:
            system = platform.system()
            
            if system == 'Windows':
                # Windows Machine GUID - стабильный идентификатор
                result = subprocess.run(
                    ['reg', 'query', r'HKLM\SOFTWARE\Microsoft\Cryptography', '/v', 'MachineGuid'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'MachineGuid' in line:
                            parts = line.split()
                            if len(parts) >= 3:
                                return parts[-1].strip()
            
            elif system == 'Darwin':
                # macOS IOPlatformUUID - стабильный идентификатор
                result = subprocess.run(
                    ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'IOPlatformUUID' in line:
                            match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', line)
                            if match:
                                return match.group(1)
            
            elif system == 'Linux':
                # Linux machine-id - стабильный идентификатор
                try:
                    with open('/etc/machine-id', 'r') as f:
                        machine_id = f.read().strip()
                        if machine_id:
                            return machine_id
                except:
                    pass
                
                # Альтернатива для Linux
                try:
                    with open('/var/lib/dbus/machine-id', 'r') as f:
                        machine_id = f.read().strip()
                        if machine_id:
                            return machine_id
                except:
                    pass
        
        except Exception:
            pass
        
        return "UNKNOWN_MACHINE_GUID"
    

    @staticmethod
    def get_motherboard_serial() -> str:
        """Получение серийного номера материнской платы - СТАБИЛЬНЫЙ идентификатор"""
        try:
            if platform.system() == 'Windows':
                result = subprocess.run(
                    ['wmic', 'baseboard', 'get', 'serialnumber'], 
                    capture_output=True, text=True, timeout=5
                )
                lines = result.stdout.strip().split('\n')
                for line in lines[1:]:
                    serial = line.strip()
                    if serial and serial != 'SerialNumber' and serial.lower() not in ['none', 'default string', 'to be filled by o.e.m.']:
                        return serial
            else:
                # Linux - через dmidecode (требует sudo, может не работать)
                result = subprocess.run(
                    ['dmidecode', '-s', 'baseboard-serial-number'], 
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout and result.returncode == 0:
                    serial = result.stdout.strip()
                    if serial and serial.lower() not in ['none', 'default string', 'to be filled by o.e.m.']:
                        return serial
        except Exception:
            pass
        return "UNKNOWN_MOTHERBOARD"
    
    @classmethod
    def generate_hwid(cls) -> str:
        """Генерация устойчивого HWID на основе СТАБИЛЬНЫХ идентификаторов"""
        # Собираем только СТАБИЛЬНЫЕ идентификаторы (удалены MAC и hostname - они нестабильны!)
        components = [
            cls.get_machine_guid(),        # Windows Machine GUID / macOS IOPlatformUUID / Linux machine-id
            cls.get_motherboard_serial(),  # Серийный номер материнской платы (стабилен)
            platform.machine(),            # Архитектура машины (стабильна)
            platform.system(),             # ОС (стабильна)
            _xor_decrypt(_SALT)            # Используем деобфусцированную соль
        ]

        # Объединяем и хешируем
        combined_string = "|".join(components)
        hwid_hash = hashlib.sha256(combined_string.encode('utf-8')).hexdigest()

        # Форматируем в виде групп по 8 символов
        formatted_hwid = '-'.join([hwid_hash[i:i+8].upper() for i in range(0, 32, 8)])

        return formatted_hwid

if __name__ == "__main__":
    hwid = HWIDGenerator.generate_hwid()
    print(f"Generated HWID: {hwid}")