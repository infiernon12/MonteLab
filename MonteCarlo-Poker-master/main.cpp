// main_daemon.cpp - DAEMON VERSION для MonteLab
// Добавляет daemon режим к существующему Monte Carlo Poker
// 
// Совместим с оригинальным кодом - старый режим работает как прежде!
// Просто замените main.cpp на этот файл и пересоберите.

// main_daemon.cpp - DAEMON VERSION для MonteLab
// Добавляет daemon режим к существующему Monte Carlo Poker
// Совместим с оригинальным кодом - старый режим работает как прежде!
// Просто замените main.cpp на этот файл и пересоберите.

#include <iostream>
#include <sstream>
#include <vector>
#include <algorithm>
#include <string>
#include "simulator.h"
using namespace std;

bool isValidCard(const string& card) {
    if (card.length() != 2) return false;
    char rank = card[0];
    char suit = card[1];
    bool valid_rank = (rank >= '2' && rank <= '9') ||
                      rank == 'T' || rank == 'J' ||
                      rank == 'Q' || rank == 'K' || rank == 'A';
    bool valid_suit = suit == 'c' || suit == 'd' ||
                      suit == 'h' || suit == 's';
    return valid_rank && valid_suit;
}

vector<string> parseCards(const string& input) {
    vector<string> cards;
    if (input.empty()) return cards;
    stringstream ss(input);
    string card;
    while (getline(ss, card, ',')) {
        card.erase(remove(card.begin(), card.end(), ' '), card.end());
        if (!card.empty() && isValidCard(card)) {
            cards.push_back(card);
        } else if (!card.empty()) {
            cerr << "Invalid card: " << card << endl;
            return {};
        }
    }
    return cards;
}

void runDaemonMode() {
    try {
        cerr << "Loading lookup table..." << endl;
        Simulator sim;
        cerr << "Lookup table loaded successfully" << endl;

        cout << "READY" << endl;
        cout.flush();

        // Маркер для лог-контроля (stderr: всегда при старте!)
        cerr << "[DAEMON MARKER] Start: main.cpp compiled and running" << endl;

        string command;
        bool marker_sent = false;
        while (getline(cin, command)) {
            command.erase(command.find_last_not_of(" \n\r\t") + 1);
            if (command == "EXIT") {
                cerr << "Received EXIT command" << endl;
                break;
            }
            if (command.substr(0, 5) == "CALC ") {
                // Маркер на первом CALC-запросе ОДИН РАЗ на stdout
                if (!marker_sent) {
                    cout << "{\"marker\": \"daemon-main.cpp-control-20251021\"}" << endl;
                    cout.flush();
                    marker_sent = true;
                }
                try {
                    string params = command.substr(5);
                    vector<string> parts;
                    stringstream ss(params);
                    string part;
                    while (getline(ss, part, '|')) {
                        parts.push_back(part);
                    }
                    if (parts.size() != 4) {
                        cout << "{\"error\": \"Invalid command format. Expected: CALC board|hole|opponents|iterations\"}" << endl;
                        cout.flush();
                        continue;
                    }
                    string board_str = parts[0];
                    string hole_str = parts[1];
                    int opponents = stoi(parts[2]);
                    int iterations = stoi(parts[3]);
                    if (opponents < 1 || opponents > 8) {
                        cout << "{\"error\": \"Opponents must be 1-8\"}" << endl;
                        cout.flush();
                        continue;
                    }
                    if (iterations < 100 || iterations > 1000000) {
                        cout << "{\"error\": \"Iterations must be 100-1000000\"}" << endl;
                        cout.flush();
                        continue;
                    }
                    vector<string> comm_hand = parseCards(board_str);
                    if (comm_hand.size() > 5) {
                        cout << "{\"error\": \"Board cannot have more than 5 cards\"}" << endl;
                        cout.flush();
                        continue;
                    }
                    vector<string> hole_cards = parseCards(hole_str);
                    if (hole_cards.size() != 2) {
                        cout << "{\"error\": \"Need exactly 2 hole cards\"}" << endl;
                        cout.flush();
                        continue;
                    }
                    vector<vector<string>> known_hands = {hole_cards};
                    vector<string> all_cards = comm_hand;
                    all_cards.insert(all_cards.end(), hole_cards.begin(), hole_cards.end());
                    sort(all_cards.begin(), all_cards.end());
                    auto it = unique(all_cards.begin(), all_cards.end());
                    if (it != all_cards.end()) {
                        cout << "{\"error\": \"Duplicate cards detected\"}" << endl;
                        cout.flush();
                        continue;
                    }
                    vector<vector<int>> results = sim.compute_probabilities(
                        iterations, comm_hand, known_hands, opponents
                    );
                    double win_rate = (results[0][0] * 100.0) / iterations;
                    double tie_rate = (results[0][1] * 100.0) / iterations;
                    double lose_rate = 100.0 - win_rate - tie_rate;
                    cout << "{\"win_rate\": " << win_rate
                         << ", \"tie_rate\": " << tie_rate
                         << ", \"lose_rate\": " << lose_rate
                         << ", \"simulations_completed\": " << iterations
                         << "}" << endl;
                    cout.flush();
                } catch (const exception& e) {
                    cout << "{\"error\": \"" << e.what() << "\"}" << endl;
                    cout.flush();
                }
            } else {
                cout << "{\"error\": \"Unknown command: " << command << "\"}" << endl;
                cout.flush();
            }
        }
    } catch (const exception& e) {
        cerr << "Fatal error in daemon mode: " << e.what() << endl;
    }
}

int cardStrToInt(const string& card) {
    static const string ranks = "23456789TJQKA";
    static const string suits = "cdhs";
    int rank = ranks.find(card[0]);
    int suit = suits.find(card[1]);
    return rank + suit * 13;
}

vector<vector<int>> convertHandsToInt(const vector<vector<string>>& hands) {
    vector<vector<int>> hands_int;
    for (const auto& hand : hands) {
        vector<int> hand_int;
        for (const auto& card : hand) {
            hand_int.push_back(cardStrToInt(card));
        }
        hands_int.push_back(hand_int);
    }
    return hands_int;
}

// Legacy mode без изменений
void runLegacyMode(int argc, char* argv[]) {
    if (argc < 4) {
        cout << "Usage: ./poker_test <board_cards> <known_hands> <opponents>" << endl;
        cout << "Example: ./poker_test '9c,Th,Jd' 'Ad,Kh|2c,7d' 2" << endl;
        cout << "Board can be empty: '' for preflop" << endl;
        return;
    }
    try {
        vector<string> comm_hand = parseCards(argv[1]);
        if (comm_hand.size() > 5) {
            cerr << "Error: Board cannot have more than 5 cards" << endl;
            return;
        }
        vector<vector<string>> known_hands;
        string hands_input = argv[2];
        if (!hands_input.empty()) {
            stringstream hands_stream(hands_input);
            string hand_pair;
            while (getline(hands_stream, hand_pair, '|')) {
                vector<string> hand = parseCards(hand_pair);
                if (hand.size() != 2) {
                    cerr << "Error: Each hand must have exactly 2 cards" << endl;
                    return;
                }
                known_hands.push_back(hand);
            }
        }
        if (known_hands.empty()) {
            cerr << "Error: At least one known hand is required" << endl;
            return;
        }
        int opponents = stoi(argv[3]);
        if (opponents < 0 || opponents > 8) {
            cerr << "Error: Opponents must be 0-8" << endl;
            return;
        }
        vector<string> all_cards = comm_hand;
        for (const auto& hand : known_hands) {
            all_cards.insert(all_cards.end(), hand.begin(), hand.end());
        }
        sort(all_cards.begin(), all_cards.end());
        auto it = unique(all_cards.begin(), all_cards.end());
        if (it != all_cards.end()) {
            cerr << "Error: Duplicate cards detected" << endl;
            return;
        }
        cout << "Board: ";
        for (const auto& card : comm_hand) cout << card << " ";
        cout << (comm_hand.empty() ? "(preflop)" : "") << endl;
        cout << "Known hands: ";
        for (size_t i = 0; i < known_hands.size(); i++) {
            cout << known_hands[i][0] << known_hands[i][1];
            if (i < known_hands.size() - 1) cout << " vs ";
        }
        cout << endl;
        cout << "Opponents: " << opponents << endl;
        cout << "Simulating..." << endl;
        Simulator sim;
        int N = 100000;
        vector<vector<int>> known_hands_int = convertHandsToInt(known_hands);
        vector<vector<int>> results = sim.compute_probabilities(N, comm_hand, known_hands, opponents);
        sim.print_results(N, known_hands_int, results);
    } catch (const exception& e) {
        cerr << "Error: " << e.what() << endl;
    }
}

int main(int argc, char* argv[]) {
    if (argc > 1 && string(argv[1]) == "--daemon") {
        cerr << "Starting in DAEMON mode..." << endl;
        runDaemonMode();
    }
    else {
        runLegacyMode(argc, argv);
    }
    return 0;
}





/* 
========================================
КАК ИСПОЛЬЗОВАТЬ:
========================================

1. BACKUP оригинального main.cpp:
   copy main.cpp main.cpp.backup

2. ЗАМЕНИТЬ main.cpp на этот файл:
   copy main_daemon.cpp main.cpp

3. ПЕРЕСОБРАТЬ проект:
   
   Windows (из папки build):
   cmake ..
   cmake --build . --config Release
   
   Linux:
   mkdir -p build && cd build
   cmake ..
   make

4. ПРОТЕСТИРОВАТЬ daemon режим:
   
   ./MonteCarloPoker.exe --daemon
   
   Должно вывести: "READY"
   
   Отправить: CALC |As,Kh|2|10000
   
   Получить: {"win_rate": 85.23, "tie_rate": 1.45, "lose_rate": 13.32, "simulations_completed": 10000}
   
   Отправить: EXIT

5. LEGACY режим работает как прежде:
   ./MonteCarloPoker.exe "" "As,Kh" 2

========================================
ПРИМЕРЫ КОМАНД ДЛЯ DAEMON:
========================================

Preflop (As Kh против 2 оппонентов):
CALC |As,Kh|2|10000

Флоп (As Kh, борд Jh Ts 9c, 3 оппонента):
CALC Jh,Ts,9c|As,Kh|3|50000

Терн (As Kh, борд Jh Ts 9c 2d, 1 оппонент):
CALC Jh,Ts,9c,2d|As,Kh|1|100000

Ривер (As Kh, борд Jh Ts 9c 2d 5h, 5 оппонентов):
CALC Jh,Ts,9c,2d,5h|As,Kh|5|100000

========================================
ПОСЛЕ ПЕРЕСБОРКИ:
========================================

В hand_analyzer.py изменить:

try:
    from monte_carlo_engine_v3 import MonteCarloEngineDaemon
    self.monte_carlo_engine = MonteCarloEngineDaemon()
    logger.info("✅ Monte Carlo DAEMON enabled!")
except Exception as e:
    logger.warning(f"Daemon failed: {e}, using legacy")
    from monte_carlo_engine_v2 import MonteCarloEngine
    self.monte_carlo_engine = MonteCarloEngine()

*/
