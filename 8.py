dict_of_capital = {
    "Russia": "Moscow",
    "Canada": "Ottawa",
    "Australia": "Sidney",
    "Portugal": "Lisbon",
    "China": "Beijing"
}
list_of_country = [x for x in dict_of_capital.keys()]
list_of_country.sort()
print(dict_of_capital)
print(dict_of_capital[input("Введите название страны на англиском")])
print(list_of_country)