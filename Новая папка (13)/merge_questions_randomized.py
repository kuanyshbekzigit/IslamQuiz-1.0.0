#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Сұрақтар бөліктерін біріктіріп, толық сұрақтар базасын жасау скрипті.
Бұл скрипт сұрақтардың опцияларын араластырып, дұрыс жауаптың 
позициясын кездейсоқ етеді.
"""

import json
import os
import random

def merge_and_randomize_questions():
    """
    Барлық сұрақтар файлдарын біріктіру және дұрыс жауап позициясын 
    әртүрлі етіп араластыру
    """
    questions = []
    
    # Бірінші бөлік (questions.json)
    if os.path.exists('questions.json'):
        with open('questions.json', 'r', encoding='utf-8') as file:
            part1 = json.load(file)
            questions.extend(part1)
            print(f"questions.json: {len(part1)} сұрақ қосылды")
    
    # Екінші бөлік (questions_part2.json)
    if os.path.exists('questions_part2.json'):
        with open('questions_part2.json', 'r', encoding='utf-8') as file:
            part2 = json.load(file)
            questions.extend(part2)
            print(f"questions_part2.json: {len(part2)} сұрақ қосылды")
    
    # Үшінші бөлік (questions_part3.json)
    if os.path.exists('questions_part3.json'):
        with open('questions_part3.json', 'r', encoding='utf-8') as file:
            part3 = json.load(file)
            questions.extend(part3)
            print(f"questions_part3.json: {len(part3)} сұрақ қосылды")
    
    # Әрбір сұрақтың опцияларын араластыру
    randomized_questions = []
    
    for question in questions:
        # Опциялар мен дұрыс жауап индексін алу
        options = question["options"]
        correct_option_id = question["correct_option_id"]
        correct_answer = options[correct_option_id]
        
        # Опцияларды араластыру үшін индекстер тізімін жасау
        indices = list(range(len(options)))
        random.shuffle(indices)
        
        # Араластырылған опциялар тізімін жасау
        shuffled_options = [options[i] for i in indices]
        
        # Дұрыс жауаптың жаңа индексін табу
        new_correct_option_id = shuffled_options.index(correct_answer)
        
        # Жаңа сұрақ объектісін жасау
        new_question = {
            "question": question["question"],
            "options": shuffled_options,
            "correct_option_id": new_correct_option_id,
            "explanation": question["explanation"],
            "motivation": question["motivation"]
        }
        
        randomized_questions.append(new_question)
    
    # Толық сұрақтар базасын сақтау
    with open('questions_full.json', 'w', encoding='utf-8') as file:
        json.dump(randomized_questions, file, ensure_ascii=False, indent=4)
    
    print(f"Барлығы: {len(randomized_questions)} сұрақ араластырылып біріктірілді")
    print("Нәтиже: questions_full.json файлына сақталды")

if __name__ == "__main__":
    merge_and_randomize_questions() 