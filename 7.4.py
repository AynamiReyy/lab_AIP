from random import randint
group_1 = ["Смирнов", "Лаптев", "Альникина", "Ридер", "Санникова", "Попова", "Карнильева", "Алияров", "Еньшин", "Хайбулина"]
group_2 = ["Цой", "Кузнецов", "Яблоков", "Печкин", "Новичихин", "Дубовцов", "Иванов", "Андреев", "Олепир", "Дереполенко"]
tupi = (group_1[randint(0, 9)], group_1[randint(0, 9)], group_1[randint(0, 9)], group_1[randint(0, 9)], group_1[randint(0, 9)], group_2[randint(0, 9)], group_2[randint(0, 9)], group_2[randint(0, 9)], group_2[randint(0, 9)], group_2[randint(0, 9)])
tupi_list = [x for x in tupi]
print(tupi, len(tupi))
tupi_list.sort()
print(tupi_list)
count = 0
if "Иванов" in tupi:
    count += tupi.count("Иванов")
print(count)

