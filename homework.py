import logging
import os
import time

from http import HTTPStatus

import requests
import telegram

from dotenv import load_dotenv

import exceptions

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='error.log',
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler()
)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
BASE_URL = 'https://practicum.yandex.ru/api'
ENDPOINT = f'{BASE_URL}/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение отправлено')
    except exceptions.UnableSendMessage as error:
        message = f'Сообщение в Telegram не отправлено: {error}'
        logger.error(message)


def get_api_answer(current_timestamp):
    """Делает запрос к эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    response = homework_statuses.json()
    if homework_statuses.status_code != HTTPStatus.OK:
        logger.error(f'Эндпоинт {ENDPOINT} недоступен.')
        raise ValueError(
            f'Сервер {ENDPOINT} недоступен.'
        )
    return response


def check_response(response):
    """Проверяет ответ API на корректность."""
    homework = response['homeworks']
    if homework == []:
        return {}
    if not isinstance(response['homeworks'], list):
        return logger.info(
            'Тип данных, полученного ответа имеет некорректный тип.'
        )
    return homework


def parse_status(homework):
    """Извлечение статуса.
    Извлекает из информации о конкретной домашней работе
    статус этой работы.
    """
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        message = 'Недокументированный статус домашней работы'
        logger.error(message)
        raise KeyError(message)
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    for token in tokens:
        if token is None:
            logger.critical(f'Отсутствует переменная окружения {token}.')
            return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            for homework in homeworks:
                if homework:
                    logger.info(
                        'Сообщение об изменении статуса работы отправлено.'
                    )
                    send_message(bot, parse_status(homework))
            logger.info('Статус работы не изменился.')
            time.sleep(RETRY_TIME)
            current_timestamp = response.get('current_date')
            response = get_api_answer(current_timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
