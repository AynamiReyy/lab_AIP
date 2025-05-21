from PIL import Image, ImageDraw, ImageFont
with Image.open("картинки/открытка.jpg") as img:
    box = (390, 993, 1530, 1700)
    croped = img.crop(box)
    croped.show()
    name = input("Кого вы хотите поздравить?")
    img_draw = ImageDraw.Draw(img)
    font =  ImageFont.truetype(font = "arialbd.ttf", size = 200)
    img_draw.text((475, 1749), f"{name}", font=font)
    img.show()