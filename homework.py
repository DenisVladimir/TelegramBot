import logging
import os
import time
import requests
import telegram
from dotenv import load_dotenv
import sys
from custom_exceptions import NotHTTPSt, ErrorConnection

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICT = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Функция отправки сообщений в телеграмм."""
    try:
        return bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception as error:
        logging.error(f'Ошибка отправки сообщения в Телеграмм {error}')
    else:
        logging.info('Бот отправляет сообщение в Телеграм')


def log_send_err_message(exception, err_description):
    """Отправка сообщения об ошибке в лог и в Телеграм.
    На входе имя ошибки и описание.
    """
    message = ('В работе бота произошла ошибка: '
               f'{exception} {err_description}')
    logging.error(message)
    logging.info('Бот отправляет в Телеграм сообщение ')
    send_message(message)


def get_api_answer(current_timestamp):
    """Функция запроса данных к Яндексу."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    hw_valid_json = dict()
    request_input_parameters = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': params
    }
    try:
        response = requests.get(**request_input_parameters)
        if response.status_code != requests.codes.ok:
            message = 'Сервер не вернул статус 200. Повторите запрос'
            raise NotHTTPSt(message)
    except requests.ConnectionError as e:
        message = 'Ошибка соединения с сервиром Яндекс-практикум'
        raise ErrorConnection(e, message)
    except requests.Timeout as e:
        message = 'Ошибка  Timeout-a.'
        raise TimeoutError(e, message)
    else:
        hw_valid_json = response.json()
        return hw_valid_json


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        logging.error('В ответе API не словарь')
        raise TypeError('В ответе не словарь')
    if not isinstance(response['homeworks'], list):
        logging.error('В ответе API в словаре не список')
        raise TypeError('В ответе не список')
    return response['homeworks']


def parse_status(homework):
    """Функция проверки статуса."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('Отсутствует ключ "homework_name')
    homework_status = homework.get('status')
    if homework_status is None:
        raise KeyError('Отсутствует ключ "status"')
    verdict = HOMEWORK_VERDICT.get(homework_status)
    if verdict:
        return (
            'Изменился статус проверки работы '
            f'"{homework_name}". {verdict}'
        )
    raise KeyError(f'Нет такого статуса - {homework_status} в списке')


def check_tokens():
    """Функция проверки всех необходимых переменных."""
    return all([PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN])


def main():
    """Основная логика работы бота."""
    logging.info('Старт Бота')
    if not check_tokens():
        log_send_err_message(
            'NO VARIABLES',
            'Не найдены необходимые переменные для работы программы'
        )
        sys.exit(
            'Значение переменны',
            '(PRACTICUM_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN)',
            'или одна из них не обнаружены'
        )
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    old_status_message = None  # Статус работы в придыдущем запросе
    while True:
        try:
            response = get_api_answer(current_timestamp)
            last_homeworks = check_response(response)
            status_message = parse_status(
                last_homeworks[0]
            )
            if (
                old_status_message or status_message == old_status_message
            ):
                old_status_message = status_message
            else:
                try:
                    send_message(bot, status_message)
                except Exception as error:
                    logging.critical(
                        f'Ошибка отправки сообщения в телеграмм {error}'
                    )
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = 'Сбой в работе программы:'
            log_send_err_message(message, error)
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
