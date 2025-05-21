from PIL import Image
with Image.open("1.jpg") as img:
    img.show()
    print(img.size)
    print(img.format)
    print(img.mode)
    img.reduce(3)
    miror_img = img.transpose(Image.FLIP_LEFT_RIGHT)
    miror_img = miror_img.transpose(Image.FLIP_TOP_BOTTOM)
    miror_img.save("new_img.jpg")

