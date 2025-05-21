tuply = ("Пнд", "Вт", "Ср" , "Чт", "Пт", "Суб", "Вс")
lis = [x for x in tuply]
a = int(input("сколько выходных на неделе он хочет"))
print(f'Ваши выходные дни:')
for i in range(a):
    print(lis.pop())
print("Ваши рабочие дни:")
for j in range(((len(tuply)) - a)):
    print(lis.pop())
