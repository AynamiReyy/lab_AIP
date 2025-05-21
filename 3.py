def eqw(date):
    num_of_day = int(date[:2])
    num_of_mounth = int(date[3:5])
    end_num_in_year = int(date[8:])
    if num_of_day * num_of_mounth == end_num_in_year:
        return True
    else:
        return False


print(eqw(date=input()))
