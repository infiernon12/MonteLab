#include "simulator.h"
#include <iostream>
#include <vector>
#include <chrono>

int main() {
    // Загружаем симулятор
    Simulator sim;
    
    // Задаем известные руки игроков
    std::vector<std::vector<std::string>> known_hands = {
        {"Ad", "Kh"},  // Туз пик, Король черв
        {"2c", "7d"}   // Двойка треф, Семерка бубен
    };
    
    // Задаем карты на столе (от 0 до 5 карт)
    std::vector<std::string> comm_hand = {"9c"}; // Девятка треф
    
    // Количество симуляций Монте-Карло
    int N = 100000;
    
    // Запускаем симуляцию (последний параметр - количество случайных противников)
    auto start = std::chrono::high_resolution_clock::now();
    
    std::vector<std::vector<int>> results = sim.compute_probabilities(N, comm_hand, known_hands, 3);
    
    auto end = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
    
    std::cout << "Время выполнения: " << duration.count() << "ms" << std::endl;
    
    return 0;
}
