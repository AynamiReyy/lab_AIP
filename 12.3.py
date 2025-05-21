def create_russian_english_dictionary(input_file, output_file):
    ru_en_dict = {}

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or '-' not in line:
                    continue

                en_part, ru_part = line.split('-', 1)
                en_word = en_part.strip()
                ru_translations = [t.strip() for t in ru_part.split(',')]

                for ru_word in ru_translations:
                    if ru_word in ru_en_dict:
                        if en_word not in ru_en_dict[ru_word]:
                            ru_en_dict[ru_word].append(en_word)
                    else:
                        ru_en_dict[ru_word] = [en_word]

        sorted_ru_words = sorted(ru_en_dict.keys())

        with open(output_file, 'w', encoding='utf-8') as f:
            for ru_word in sorted_ru_words:
                en_words = ', '.join(sorted(ru_en_dict[ru_word]))
                f.write(f"{ru_word} - {en_words}\n")

        print(f"Русско-английский словарь успешно создан в файле {output_file}")

    except FileNotFoundError:
        print(f"Ошибка: файл {input_file} не найден")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")


create_russian_english_dictionary('en-ru.txt', 'ru-en.txt')