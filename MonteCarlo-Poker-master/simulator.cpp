//
// Fixed simulator.cpp with memory and bounds safety fixes
//

#include <vector>
#include <iostream>
#include <algorithm>
#include "simulator.h"
#include "tools.h"
#include "samples.h" 
#include "cards.h"

using namespace std;

int Simulator::to_ckey(const vector<int> &hand)
{
    int key = 0;
    for (size_t i = 0; i < hand.size(); ++i)
    {
        // ИСПРАВЛЕНИЕ: Добавлена проверка границ для c_table
        int table_index = (i + 1) * 53 + hand[i];
        if (table_index >= 0 && table_index < static_cast<int>(c_table.size())) {
            key += c_table[table_index];
        } else {
            cerr << "[Error] Index out of bounds in to_ckey: " << table_index << endl;
            return 0;
        }
    }
    return key;
}

vector<int> Simulator::get_remaining(vector<int> &comm_hand, vector<vector<int>> &known_hands){
    vector<int> remaining;
    vector<int> filled(52, 0);

    for (int card : comm_hand){
        if (card >= 0 && card < 52) {
            filled[card] = 1;
        }
    }

    for (const vector<int> &known_hand : known_hands){
        for (int card : known_hand){
            if (card >= 0 && card < 52) {
                filled[card] = 1;
            }
        }
    }

    for (int i = 0; i < 52; ++i){
        if (!filled[i]){
            remaining.push_back(i);
        }
    }

    return remaining;
}

vector<vector<int>> Simulator::fill_empty(int N, vector<int> &comm_hand, vector<vector<int>> &known_hands, int players_unknown){
    vector<int> remaining = get_remaining(comm_hand, known_hands);
    int c = players_unknown * 2 + 5 - static_cast<int>(comm_hand.size());

    if (static_cast<int>(remaining.size()) < c) {
        cerr << "[Error] Not enough cards remaining to fill empty slots" << endl;
        return {};
    }

    vector<vector<int>> samples = gen_samples(N, c, static_cast<int>(remaining.size()));

    for (vector<int> &sample : samples)
    {
        for (int i = 0; i < c && i < static_cast<int>(sample.size()); ++i)
        {
            if (sample[i] >= 0 && sample[i] < static_cast<int>(remaining.size())) {
                sample[i] = remaining[sample[i]];
            } else {
                cerr << "[Warning] Sample index out of range" << endl;
            }
        }
    }

    return samples;
}

int Simulator::evaluate_selection(vector<int> selection){
    sort(selection.begin(), selection.end());
    vector<int> hand(5);
    
    if (selection.size() < 7) {
        cerr << "[Error] Selection vector size less than 7" << endl;
        return -1;
    }
    
    for (int i = 0; i < 5; ++i){
        hand[i] = selection[i + 2];
    }

    int key = to_ckey(hand);
    
    // ИСПРАВЛЕНИЕ: Проверка границ для table
    if (key < 0 || key >= static_cast<int>(table.size())) {
        cerr << "[Error] Key out of bounds in evaluate_selection: " << key << endl;
        return 0;
    }
    
    int max_score = table[key];

    for (int j = 0; j < 40; j += 2){
        // ИСПРАВЛЕНИЕ: Дополнительные проверки границ
        if (j + 1 >= static_cast<int>(replace.size()) || 
            replace[j] >= 5 || replace[j + 1] >= static_cast<int>(selection.size())) {
            continue;
        }
        
        int ix_k = (replace[j] + 1) * 53;
        
        // Проверка границ для c_table
        int index1 = ix_k + selection[replace[j + 1]];
        int index2 = ix_k + hand[replace[j]];
        
        if (index1 >= 0 && index1 < static_cast<int>(c_table.size()) &&
            index2 >= 0 && index2 < static_cast<int>(c_table.size())) {
            
            key += c_table[index1] - c_table[index2];
            hand[replace[j]] = selection[replace[j + 1]];
            
            if (key >= 0 && key < static_cast<int>(table.size())) {
                max_score = max(max_score, table[key]);
            }
        }
    }
    return max_score;
}

void Simulator::update_winners(int my_val, int &max_val, int ix, vector<int> &winners){
    if (my_val > max_val){
        winners.clear();
        winners.push_back(ix);
        max_val = my_val;
    }
    else if (my_val == max_val){
        winners.push_back(ix);
    }
}

vector<int> Simulator::simulate(vector<int> &selection, vector<vector<int>> &known_hands, vector<int> &sample, int start){
    vector<int> winners;
    int max_val = 0;

    if (selection.size() < 7) {
        selection.resize(7);
    }

    for (size_t i = 0; i < known_hands.size(); i++){
        if (known_hands[i].size() < 2) continue;

        selection[5] = known_hands[i][0];
        selection[6] = known_hands[i][1];

        int eval_result = evaluate_selection(selection);
        if (eval_result >= 0) {
            update_winners(eval_result, max_val, static_cast<int>(i), winners);
        }
    }

    for (int i = 0; start + i * 2 + 1 < static_cast<int>(sample.size()); i++){
        selection[5] = sample[start + i * 2];
        selection[6] = sample[start + i * 2 + 1];

        int eval_result = evaluate_selection(selection);
        if (eval_result >= 0) {
            update_winners(eval_result, max_val, static_cast<int>(known_hands.size()) + i, winners);
        }
    }

    return winners;
}

vector<vector<int>> Simulator::calculate(int N, vector<int> comm_hand, vector<vector<int>> known_hands, int players_unknown){
    vector<vector<int>> samples = fill_empty(N, comm_hand, known_hands, players_unknown);
    if (samples.empty()) {
        cerr << "[Error] No samples available for calculation" << endl;
        return {};
    }
    
    vector<int> selection(7);
    vector<vector<int>> results(known_hands.size() + players_unknown, vector<int>(2, 0));

    for (size_t i = 0; i < comm_hand.size() && i < 7; ++i){
        selection[i] = comm_hand[i];
    }
    
    int s_comm = 5 - static_cast<int>(comm_hand.size());

    for (const vector<int> &sample : samples){
        for (int i = 0; i < s_comm && i < static_cast<int>(sample.size()); ++i){
            if (4 - i >= 0 && 4 - i < 7) {
                selection[4 - i] = sample[i];
            }
        }

        vector<int> winners = simulate(selection, known_hands, const_cast<vector<int>&>(sample), s_comm);
        
        if (winners.size() == 1 && winners[0] < static_cast<int>(results.size())) {
            results[winners[0]][0]++;
        } else {
            for (int winner : winners) {
                if (winner >= 0 && winner < static_cast<int>(results.size())) {
                    results[winner][1]++;
                }
            }
        }
    }

    return results;
}

void Simulator::print_results(int N, vector<vector<int>> hands, vector<vector<int>> results) {
    for (size_t i = 0; i < hands.size() && i < results.size(); i++) {
        print_hand(hands[i]);
        format_result(N, results[i]);
    }

    int unknown = static_cast<int>(results.size()) - static_cast<int>(hands.size());
    if (unknown > 0) {
        float ties = 0;
        float wins = 0;
        float factor = 100.0/N/unknown;

        for (size_t i = hands.size(); i < results.size(); i++){
            wins += results[i][0];
            ties += results[i][1];
        }
        printf("?? ?? %6.3f  %6.3f (x%d random hands)\n", wins*factor, ties*factor, unknown);
    }
}

void Simulator::format_result(int N, vector<int> result) {
    printf("%6.3f  %6.3f\n", result[0]*100.0/N, result[1]*100.0/N);
}

// ===== ИСПРАВЛЕННАЯ ФУНКЦИЯ: БЕЗ ТАБЛИЧНОГО ВЫВОДА =====
vector<vector<int>> Simulator::compute_probabilities(int N, vector<string>& comm_hand_str, vector<vector<string>>& known_hands_str, int players_unknown){
    // Время засекаем только для внутренней диагностики (если нужно)
    // Но ничего не печатаем на stdout!
    
    vector<int> comm_hand = convert_hand(comm_hand_str);
    vector<vector<int>> known_hands;

    for (auto& known_hand_str : known_hands_str) { 
        known_hands.push_back(convert_hand(known_hand_str));
    }

    vector<vector<int>> results = calculate(N, comm_hand, known_hands, players_unknown);

    // ====== КРИТИЧНО: НИКАКОГО cout/printf НА STDOUT! ======
    // Весь вывод табличных данных только в legacy-режиме через main.cpp!
    // Здесь только возврат результата:
    
    return results;
}
