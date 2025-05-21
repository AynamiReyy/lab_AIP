def happy(num):
    sum_1 = 0
    sum_2 = 0
    for i in range(int(len(num) / 2)):
        sum_1 += int(num[i])
    for i in range(int(len(num) / 2), int(len(num))):
        sum_2 += int(num[i])
    if sum_1 == sum_2:
        return True
    else:
        return False



def chek(num):
    if len(num) % 2 == 0:
        return True
    else:
        return False

while True:
    num = input()
    if chek(num):
        break
    else:
        print("Введите число с четным количеством цифр")
print(happy(num))