#include "tools.h"
#include <vector>
#include <iostream>
#include <fstream>
#include <iterator>

using namespace std;

void print(vector<int> const &input) {
    std::copy(input.begin(),
            input.end(),
            std::ostream_iterator<int>(std::cout, " "));
}

ifstream::pos_type filesize(const char* filename)
{
    ifstream in(filename, std::ifstream::ate | std::ifstream::binary);
    if (!in.is_open()) {
        cerr << "[Error] Cannot open file: " << filename << endl;
        return 0;
    }
    ifstream::pos_type ret = in.tellg();
    in.close();
    return ret;
}

void write_vect(vector<int> vect, string name){
    if (vect.empty()) {
        cout << "Warning: Empty vector, nothing to write" << endl;
        return;
    }
    
    fstream f;
    int* arr = &vect[0];
    f.open(name, ios::out|ios::binary);
    if (f.is_open()){
        f.write(reinterpret_cast<char*>(arr), vect.size() * sizeof(int));
        f.close();
    } else {
        cout << "Error: Cannot open file for writing: " << name << endl;
    }
}

vector<int> read_vect(const char *name){
    fstream f;
    string loc = name;
    
    // ИСПРАВЛЕНИЕ: Проверка существования файла
    ifstream test_file(loc);
    if (!test_file.is_open()) {
        cerr << "[Error] Cannot open lookup table file: " << loc << endl;
        cerr << "Make sure lookup_tablev3.bin exists in the current directory" << endl;
        return vector<int>();
    }
    test_file.close();
    
    f.open(loc, ios::in|ios::binary);
    int fsize = static_cast<int>(filesize(loc.c_str()));
    
    if (fsize <= 0 || fsize % sizeof(int) != 0) {
        cerr << "[Error] Invalid file size for lookup table: " << fsize << endl;
        return vector<int>();
    }
    
    vector<int> vect(fsize / sizeof(int));
    int* arr = &vect[0];
    
    if (f.is_open()){
        f.read(reinterpret_cast<char*>(arr), fsize);
        f.close();
    } else {
        cerr << "[Error] Failed to read lookup table" << endl;
        return vector<int>();
    }
    
    return vect;
}
