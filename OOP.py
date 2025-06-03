import tkinter as tk
from tkinter import ttk, messagebox


class Restaurant:
    def __init__(self, restaurant_name, cuisine_type, initial_rating=0):
        self.restaurant_name = restaurant_name
        self.cuisine_type = cuisine_type
        self.rating = initial_rating

    def describe_restaurant(self):
        return f"Название: {self.restaurant_name}\nТип кухни: {self.cuisine_type}\nРейтинг: {self.rating}"

    def update_rating(self, new_rating):
        self.rating = new_rating
        return f"Новый рейтинг: {self.rating}"


class IceCreamStand(Restaurant):
    def __init__(self, master):
        super().__init__("Кафе-мороженое", "Десерты", 4.5)
        self.master = master
        master.title(self.restaurant_name)
        master.geometry("500x650")
        master.configure(bg="#FFF0F5")

        # Данные кафе
        self.flavors = ["Ванильное", "Шоколадное", "Клубничное", "Фисташковое", "Мятное", "Карамельное"]
        self.types = ["В стаканчике", "На палочке", "Мягкое", "Фруктовый лед", "В вафельном рожке"]
        self.location = "ул. Сладкая, 15"
        self.hours = "10:00 - 22:00"
        self.ice_cream_types = {
            'На палочке': [],
            'Мягкое': [],
            'Фруктовый лед': [],
            'В вафельном стаканчике': []
        }

        # Инициализация интерфейса
        self.create_widgets()
        self.add_sample_data()

    def add_sample_data(self):
        """Добавляем тестовые данные в типы мороженого"""
        for flavor in self.flavors[:3]:
            self.add_flavor_to_type(flavor, "На палочке")
        for flavor in self.flavors[2:]:
            self.add_flavor_to_type(flavor, "Мягкое")

    def add_flavor_to_type(self, flavor, ice_type):
        """Добавляет сорт мороженого в указанный тип"""
        if ice_type in self.ice_cream_types:
            if flavor not in self.ice_cream_types[ice_type]:
                self.ice_cream_types[ice_type].append(flavor)

    def create_widgets(self):
        """Создает все элементы интерфейса"""
        # Стиль
        style = ttk.Style()
        style.configure('TFrame', background='#FFF0F5')
        style.configure('TLabel', background='#FFF0F5', font=('Arial', 10))
        style.configure('Header.TLabel', font=('Arial', 14, 'bold'))

        # Основные фреймы
        header_frame = ttk.Frame(self.master)
        header_frame.pack(pady=10, fill='x')

        info_frame = ttk.Frame(self.master)
        info_frame.pack(pady=5, fill='x', padx=10)

        order_frame = ttk.Frame(self.master)
        order_frame.pack(pady=10, fill='x', padx=10)

        # Заголовок
        ttk.Label(
            header_frame,
            text=f"Добро пожаловать в {self.restaurant_name}!",
            style='Header.TLabel'
        ).pack()

        # Информация о кафе
        ttk.Label(info_frame, text=self.describe_restaurant()).pack(anchor='w')
        ttk.Label(info_frame, text=f"Адрес: {self.location}").pack(anchor='w')
        ttk.Label(info_frame, text=f"Часы работы: {self.hours}").pack(anchor='w')

        # Выбор мороженого
        flavor_frame = ttk.LabelFrame(order_frame, text="Выберите вкус:")
        flavor_frame.pack(fill='x', pady=5)

        self.flavor_var = tk.StringVar(value=self.flavors[0])
        for flavor in self.flavors:
            ttk.Radiobutton(
                flavor_frame,
                text=flavor,
                variable=self.flavor_var,
                value=flavor
            ).pack(anchor='w')

        # Выбор типа
        type_frame = ttk.LabelFrame(order_frame, text="Выберите тип:")
        type_frame.pack(fill='x', pady=5)

        self.type_var = tk.StringVar(value=self.types[0])
        for ice_type in self.types:
            ttk.Radiobutton(
                type_frame,
                text=ice_type,
                variable=self.type_var,
                value=ice_type
            ).pack(anchor='w')

        # Кнопки управления
        btn_frame = ttk.Frame(order_frame)
        btn_frame.pack(pady=10)

        ttk.Button(
            btn_frame,
            text="Сделать заказ",
            command=self.make_order,
            style='TButton'
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="Показать меню",
            command=self.show_menu
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame,
            text="Обновить рейтинг",
            command=self.update_rating_dialog
        ).pack(side='left', padx=5)

        # Статусная строка
        self.status_var = tk.StringVar()
        ttk.Label(
            order_frame,
            textvariable=self.status_var,
            foreground='green',
            font=('Arial', 9)
        ).pack(pady=5)

    def make_order(self):
        """Обработка заказа мороженого"""
        flavor = self.flavor_var.get()
        ice_type = self.type_var.get()

        if not self.check_availability(flavor, ice_type):
            messagebox.showwarning("Нет в наличии",
                                   f"К сожалению, {flavor.lower()} {ice_type.lower()} сейчас нет в меню!")
            return

        message = f"Вы заказали: {flavor.lower()} мороженое {ice_type.lower()}!"
        messagebox.showinfo("Заказ принят", message)
        self.status_var.set(f"Последний заказ: {flavor} ({ice_type})")

    def check_availability(self, flavor, ice_type):
        """Проверяет наличие мороженого в меню"""
        if ice_type in self.ice_cream_types:
            return flavor in self.ice_cream_types[ice_type]
        return True  # Если тип не указан в словаре, считаем что есть

    def show_menu(self):
        """Показывает полное меню кафе"""
        menu_text = "Наше меню:\n\n"
        for ice_type, flavors in self.ice_cream_types.items():
            menu_text += f"{ice_type}:\n"
            menu_text += "\n".join(f"  - {flavor}" for flavor in flavors) + "\n\n"

        messagebox.showinfo("Меню кафе", menu_text)

    def update_rating_dialog(self):
        """Диалог обновления рейтинга"""
        new_rating = simpledialog.askfloat(
            "Обновить рейтинг",
            "Введите новый рейтинг (0-5):",
            parent=self.master,
            minvalue=0,
            maxvalue=5,
            initialvalue=self.rating
        )

        if new_rating is not None:
            self.update_rating(new_rating)
            messagebox.showinfo("Успешно", f"Рейтинг обновлен: {self.rating}")
            self.status_var.set(f"Рейтинг обновлен: {self.rating}")


# Запуск приложения
if __name__ == "__main__":
    try:
        from tkinter import simpledialog

        root = tk.Tk()
        app = IceCreamStand(root)
        root.mainloop()
    except ImportError as e:
        print(f"Ошибка: {e}\nУбедитесь, что Tkinter установлен правильно.")