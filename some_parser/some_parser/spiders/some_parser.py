from datetime import datetime
import os
import re
import time

import scrapy
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from scrapy.http import HtmlResponse

load_dotenv()

AGE_BUTTON = os.getenv("AGE_BUTTON")
CHANGE_CITY_BUTTON = os.getenv("CHANGE_CITY_BUTTON")
KRASNODAR_BUTTON = os.getenv("KRASNODAR_BUTTON")

PRODUCT_ARTICUL = os.getenv("PRODUCT_ARTICUL")
PRODUCT_AVAILABILITY_TEXT = os.getenv("PRODUCT_AVAILABILITY_TEXT")
PRODUCT_AVAILABILITY_SHOP = os.getenv("PRODUCT_AVAILABILITY_SHOP")
PRODUCT_BRAND = os.getenv("PRODUCT_BRAND")
PRODUCT_COUNTRY = os.getenv("PRODUCT_COUNTRY")
PRODUCT_DESCRIPTION = os.getenv("PRODUCT_DESCRIPTION")
PRODUCT_IMAGES = os.getenv("PRODUCT_IMAGES")
PRODUCT_LINK = os.getenv("PRODUCT_LINK")
PRODUCT_CURRENT_PRICE = os.getenv("PRODUCT_CURRENT_PRICE")
PRODUCT_ORIGINAL_PRICE = os.getenv("PRODUCT_ORIGINAL_PRICE")
PRODUCT_SECTION = os.getenv("PRODUCT_SECTION")
PRODUCT_TITLE = os.getenv("PRODUCT_TITLE")
PRODUCT_TYPE = os.getenv("PRODUCT_TYPE")
PRODUCT_VOLUME = os.getenv("PRODUCT_VOLUME")

ALLOWEED_DOMAINS = os.getenv("ALLOWEED_DOMAINS").split(",")
ENCODING = os.getenv("ENCODING")
START_URLS = os.getenv("START_URLS").split(",")


class SomeSpider(scrapy.Spider):
    """
    Spider для сбора информации о товарах с сайта alkoteka.com
    с учетом региона Краснодар.
    """
    name = "some_parser"
    allowed_domains = ALLOWEED_DOMAINS
    start_urls = START_URLS

    def __init__(self):
        options = Options()
        # Чтобы не видеть браузер надо раскомментить.
        # options.add_argument("--headless")
        self.driver = webdriver.Firefox(options=options)
        self.wait = WebDriverWait(self.driver, 10)

    def parse(self, response):
        self.driver.get(response.url)
        time.sleep(3)

        try:
            age_button = self.driver.find_element(
                By.CSS_SELECTOR,
                AGE_BUTTON,
            )
            age_button.click()
            time.sleep(2)
        except Exception as error:
            self.logger.info(
                f"Кнопка подтверждения возраста не найдена: {error}."
            )

        try:
            change_city_button = self.wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                CHANGE_CITY_BUTTON,
            )))
            change_city_button.click()
            self.logger.info("Нажата кнопка 'Изменить'.")
            time.sleep(1)
        except Exception as error:
            self.logger.info(f"Не удалось нажать 'Изменить': {str(error)}.")

        try:
            krasnodar_button = self.wait.until(
                EC.element_to_be_clickable(
                    (
                        By.CSS_SELECTOR,
                        KRASNODAR_BUTTON,
                    )
                )
            )
            krasnodar_button.click()
            self.logger.info("Город выбран: Краснодар.")
            time.sleep(2)
        except Exception as error:
            self.logger.info(f"Не удалось выбрать Краснодар: {str(error)}.")

        self.scroll_page(scroll_pause_time=2, max_scrolls=15)

        html = self.driver.page_source
        sel_response = HtmlResponse(
            url=self.driver.current_url,
            body=html,
            encoding=ENCODING,
        )

        product_links = sel_response.css(PRODUCT_LINK).getall()

        if not product_links:
            self.logger.warning("Ссылки на карточки товаров не найдены.")
        else:
            self.logger.info(f"Найдено товаров: {len(product_links)}.")
        for href in product_links:
            full_url = response.urljoin(href)
            yield scrapy.Request(full_url, callback=self.parse_product)

    def scroll_page(self, scroll_pause_time=2, max_scrolls=10):
        last_height = self.driver.execute_script(
            "return document.body.scrollHeight"
        )
        for _ in range(max_scrolls):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(scroll_pause_time)
            new_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            if new_height == last_height:
                break
            last_height = new_height

    def parse_product(self, response):
        self.logger.info(f"Парсинг карточки товара: {response.url}.")
        self.driver.get(response.url)

        rpc = re.search(r"_(\d+)$", response.url).group(1)

        try:
            title = self.wait.until(
                EC.presence_of_element_located((By.XPATH, PRODUCT_TITLE))
            )
            title = title.text
        except Exception as error:
            self.logger.warning(f"Не удалось найти заголовок: {error}.")
            title = None

        try:
            brand = self.wait.until(
                EC.presence_of_element_located((By.XPATH, PRODUCT_BRAND))
            )
            brand = brand.text
        except Exception as error:
            self.logger.warning(f"Не удалось найти бренд: {error}.")
            brand = None

        try:
            section = self.wait.until(
                EC.presence_of_element_located((By.XPATH, PRODUCT_SECTION))
            )
            section = section.text
        except Exception as error:
            self.logger.warning(f"Не удалось найти секции: {error}.")
            section = None

        try:
            current_price = self.driver.find_element(
                By.XPATH, PRODUCT_CURRENT_PRICE
            )
            current_price = float(
                current_price.text.replace("₽", "").replace(" ", "").strip()
            )

            try:
                original_price = self.driver.find_element(
                    By.XPATH, PRODUCT_ORIGINAL_PRICE
                )
                original_price = float(
                    original_price.text.replace(
                        "₽", ""
                    ).replace(" ", "").strip()
                )
            except Exception:
                original_price = current_price

            sale_tag = ""
            if original_price != current_price:
                discount = round(
                    (original_price - current_price) / original_price * 100
                )
                sale_tag = f"Скидка {discount}%."

            price_data = {
                "current": current_price,
                "original": original_price,
                "sale_tag": sale_tag
            }
        except Exception as error:
            self.logger.warning(f"Ошибка при получении цен: {error}.")
            price_data = {
                "current": None,
                "original": None,
                "sale_tag": ""
            }

        try:
            availability = self.driver.find_element(
                By.XPATH, PRODUCT_AVAILABILITY_TEXT
            )
            availability_shop = self.driver.find_element(
                By.XPATH, PRODUCT_AVAILABILITY_SHOP
            )
            availability_text = availability.text.strip().lower()
            in_stock = "можно забрать из" in availability_text
            match = re.search(r"\d+", availability_shop.text)
            count = int(match.group()) if match else 0
        except Exception:
            in_stock = False
            count = 0
        stock = {
            "in_stock": in_stock,
            "count": count
        }

        try:
            image_element = self.driver.find_element(
                By.XPATH, PRODUCT_IMAGES
            )
            image = image_element.get_attribute("src")
        except Exception as error:
            self.logger.warning(f"Ошибка при получении изображения: {error}.")
            image = ""

        metadata = {}
        try:
            description = self.driver.find_element(
                By.XPATH, PRODUCT_DESCRIPTION
            )
            metadata["Описание"] = description
        except Exception as error:
            self.logger.warning(f"Не удалось получить описание: {error}.")
        try:
            articul = self.driver.find_element(
                By.XPATH, PRODUCT_ARTICUL
            )
            metadata["Артикул"] = articul.text.strip()
        except Exception as error:
            self.logger.warning(f"Не удалось получить артикул: {error}.")
        try:
            type = self.driver.find_element(By.XPATH, PRODUCT_TYPE)
            metadata["Тип"] = type.text.strip()
        except Exception as error:
            self.logger.warning(f"Не удалось получить тип: {error}.")
        try:
            country = self.driver.find_element(
                By.XPATH, PRODUCT_COUNTRY
            )
            metadata["Страна"] = country.text.strip()
        except Exception as error:
            self.logger.warning(
                f"Не удалось получить страну производителя: {error}."
            )
        try:
            volume = self.driver.find_element(By.XPATH, PRODUCT_VOLUME)
            metadata["Объем"] = volume.text.strip()
        except Exception as error:
            self.logger.warning(f"Не удалось получить объем: {error}.")

        try:
            volume_options = self.driver.find_elements(
                By.XPATH, PRODUCT_VOLUME
            )
            variants = len(volume_options)
        except Exception as error:
            self.logger.warning(
                f"Не удалось получить варианты объема товара: {error}."
            )
            variants = 0                                           

        yield {
            "timestamp": datetime.now(),
            "rpc": rpc,
            "url": response.url,
            "title": title,
            "brand": brand,
            "section": section,
            "price_data": price_data,
            "stock": stock,
            "main_img": image,
            "metadata": metadata,
            "variants": variants,
        }

    def closed(self, reason):
        """
        Завершает работу Selenium после окончания парсинга.
        """
        self.driver.quit()
