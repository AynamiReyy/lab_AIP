from PIL import Image
link_on_hollyday = {
    "8 МАРТА" : "картинки/8 марта.jpg",
    "1 МАЙ" : 'картинки/1 май.jpg',
    "НОВЫЙ ГОД" : "картинки/новый год.jpg",
    "ДЕНЬ РОЖДЕНИЯ" : "картинки/открытка.jpg"
}
with Image.open(link_on_hollyday[input().upper()]) as img:
    img.show()