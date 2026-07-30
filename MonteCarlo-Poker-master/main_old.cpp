#include <iostream>
#include <sstream>
#include <vector>
#include <algorithm>
#include "simulator.h"
using namespace std;

bool isValidCard(const string& card) {
    if (card.length() != 2) return false;
    
    char rank = card[0];
    char suit = card[1];
    
    // Валидные ранги: 2-9, T, J, Q, K, A
    bool valid_rank = (rank >= '2' && rank <= '9') || 
                      rank == 'T' || rank == 'J' || 
                      rank == 'Q' || rank == 'K' || rank == 'A';
    
    // Валидные масти: c, d, h, s
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
        // Убираем пробелы
        card.erase(remove(card.begin(), card.end(), ' '), card.end());
        
        if (!card.empty() && isValidCard(card)) {
            cards.push_back(card);
        } else if (!card.empty()) {
            cerr << "Invalid card: " << card << endl;
            return {}; // Возвращаем пустой вектор при ошибке
        }
    }
    return cards;
}

int main(int argc, char* argv[]) {
    if (argc < 4) {
        cout << "Usage: ./poker_test <board_cards> <known_hands> <opponents>" << endl;
        cout << "Example: ./poker_test '9c,Th,Jd' 'Ad,Kh|2c,7d' 2" << endl;
        cout << "Board can be empty: '' for preflop" << endl;
        return 1;
    }
    
    try {
        // Парсинг board cards с валидацией
        vector<string> comm_hand = parseCards(argv[1]);
        if (comm_hand.size() > 5) {
            cerr << "Error: Board cannot have more than 5 cards" << endl;
            return 1;
        }
        
        // Парсинг known hands с валидацией
        vector<vector<string>> known_hands;
        string hands_input = argv[2];
        
        if (!hands_input.empty()) {
            stringstream hands_stream(hands_input);
            string hand_pair;
            
            while (getline(hands_stream, hand_pair, '|')) {
                vector<string> hand = parseCards(hand_pair);
                
                if (hand.size() != 2) {
                    cerr << "Error: Each hand must have exactly 2 cards, got " 
                         << hand.size() << " in '" << hand_pair << "'" << endl;
                    return 1;
                }
                
                known_hands.push_back(hand);
            }
        }
        
        if (known_hands.empty()) {
            cerr << "Error: At least one known hand is required" << endl;
            return 1;
        }
        
        // Валидация количества противников
        int opponents = stoi(argv[3]);
        if (opponents < 0 || opponents > 8) {
            cerr << "Error: Opponents must be 0-8, got " << opponents << endl;
            return 1;
        }
        
        // Проверка на дубликаты карт
        vector<string> all_cards = comm_hand;
        for (const auto& hand : known_hands) {
            all_cards.insert(all_cards.end(), hand.begin(), hand.end());
        }
        
        sort(all_cards.begin(), all_cards.end());
        auto it = unique(all_cards.begin(), all_cards.end());
        if (it != all_cards.end()) {
            cerr << "Error: Duplicate cards detected" << endl;
            return 1;
        }
        
        // Отладочная информация
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
        
        // Создаем симулятор и запускаем расчет
        Simulator sim;
        int N = 100000;
        
        vector<vector<int>> results = sim.compute_probabilities(N, comm_hand, known_hands, opponents);
        
        // JSON вывод для Python интеграции
        cout << "\n{\"results\":[";
        for (size_t i = 0; i < results.size() && i < known_hands.size(); ++i) {
            cout << "{\"hand\":\"" << known_hands[i][0] << known_hands[i][1] 
                 << "\",\"win\":" << results[i][0] 
                 << ",\"tie\":" << results[i][1] << "}";
            if (i < results.size() - 1 && i < known_hands.size() - 1) cout << ",";
        }
        cout << "],\"simulations\":" << N << "}" << endl;
        
        // ИСПРАВЛЕНИЕ: Нормальный выход без принудительного exit(0)
        return 0;
        
    } catch (const invalid_argument& e) {
        cerr << "Error parsing opponents count: " << argv[3] << endl;
        return 1;
    } catch (const exception& e) {
        cerr << "Unexpected error: " << e.what() << endl;
        return 1;
    }
}
