import logging
import os
import time
import requests
import telegram
from dotenv import load_dotenv
load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 10
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Функция отправки сообщений в телеграмм."""
    return bot.send_message(TELEGRAM_CHAT_ID, message)


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
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        if response.status_code != requests.codes.ok:
            message = 'Сервер домашки не вернул статус 200.'
            log_send_err_message('Not HTTPStstus.OK', message)
            return {}
    except requests.ConnectionError as e:
        message = 'Ошибка соединения.'
        log_send_err_message(e, message)
    except requests.Timeout as e:
        message = 'Ошибка  Timeout-a.'
        log_send_err_message(e, message)
    except requests.RequestException as e:
        message = 'Ошибка отправки запроса.'
        log_send_err_message(e, message)
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
    if homework_status in HOMEWORK_STATUSES:
        verdict = HOMEWORK_STATUSES[homework_status]
        return (
            f'Изменился статус проверки работы '
            f'"{homework_name}". {verdict}'
        )
    raise KeyError(f'Нет такого статуса - {homework_status} в списке')


def check_tokens():
    """Функция проверки всех необходимых переменных."""
    if PRACTICUM_TOKEN and TELEGRAM_CHAT_ID and TELEGRAM_TOKEN:
        return True
    return False


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())  # int(time.time()) - (10 *86400)
    old_status_message = None  # Статус работы в придыдущем запросе
    while True:
        try:
            print('Bot work')
            response = get_api_answer(current_timestamp)
            last_homeworks = check_response(response)
            if isinstance(last_homeworks, list) and last_homeworks:
                status_message = parse_status(
                    last_homeworks[0]
                )
                if (
                    old_status_message or status_message == old_status_message
                ):
                    old_status_message = status_message
                    print(f'статус не изменился: {status_message}')
                else:
                    print('отпрвка смс пользователя')
                    logging.info('Бот отправляет сообщение в Телеграм')
                    try:
                        send_message(bot, status_message)
                    except Exception as error:
                        logging.critical(
                            f'Ошибка отправки сообщения в телеграмм {error}'
                        )
            else:
                message = ''
                log_send_err_message('')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
