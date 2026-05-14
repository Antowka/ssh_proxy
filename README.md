# SSH SOCKS Proxy

SOCKS5 прокси сервер на базе SSH туннеля. Позволяет маршрутизировать трафик через удаленный SSH сервер.

## Принцип работы

```
Клиент -> :8787 (SOCKS5) -> SSH Сервер -> Интернет
```

## Шаг 1 - Клонирование репозитория

```bash
git clone <URL_репозитория> /opt/ssh_proxy
cd /opt/ssh_proxy
```

## Шаг 2 - Установка зависимостей

```bash
apt update
apt install -y python3 python3-pip
pip3 install paramiko
```

## Шаг 3 - Настройка

Откройте `ssh_proxy.py` и измените параметры подключения к вашему SSH серверу:

```python
HOST = "your-ssh-server.com"      # Адрес SSH сервера
PORT = 22                          # SSH порт (по умолчанию 22)
USER = "username"                 # Имя пользователя SSH
PASSWORD = "your_password"        # Пароль SSH
PROXY_PORT = 8787                  # Порт SOCKS прокси (любой свободный)
RECONNECT_DELAY = 5                # Пауза перед переподключением (сек)
```

## Шаг 4 - Запуск и проверка

Запустите сервис вручную для проверки:

```bash
python3 /opt/ssh_proxy/ssh_proxy.py
```

Если в логах появилось `Connected to <SERVER>` и `SOCKS proxy listening on 0.0.0.0:8787` - всё работает.

Для остановки нажмите `Ctrl+C`.

## Шаг 5 - Установка как systemd сервис (автозапуск)

Скопируйте unit файл:

```bash
cp /opt/ssh_proxy/ssh-proxy.service /etc/systemd/system/
```

Перезагрузите systemd:

```bash
systemctl daemon-reload
```

Включите автозапуск:

```bash
systemctl enable ssh-proxy
```

Запустите:

```bash
systemctl start ssh-proxy
```

## Управление сервисом

```bash
systemctl status ssh-proxy   # Проверить статус
systemctl restart ssh-proxy  # Перезапустить
systemctl stop ssh-proxy     # Остановить
```

## Просмотр логов

```bash
tail -f /opt/ssh_proxy/ssh-proxy.log
```

## Настройка клиентов

### Браузер (Firefox)

1. Меню -> Настройки -> Прокси
2. Выберите "Ручная настройка прокси"
3. SOCKS Host: `127.0.0.1`
4. Порт: `8787`
5. Отметьте "SOCKS v5"
6. Нажмите "OK"

### Браузер (Chrome)

Используйте расширение типа "SwitchyOmega" или "Proxifier".

### curl

```bash
curl --socks5 127.0.0.1:8787 http://example.com
```

### Терминал (все приложения)

```bash
export all_proxy="socks5://127.0.0.1:8787"
```

## Возможные проблемы

| Ошибка | Причина | Решение |
|--------|---------|---------|
| `Temporary failure in name resolution` | Не работает DNS | Проверьте `/etc/resolv.conf` |
| `Connection timed out` | SSH сервер недоступен | Проверьте HOST, PORT, файрвол |
| `Authentication failed` | Неверный логин/пароль | Проверьте USER и PASSWORD |
| `SSH transport not active` | Соединение разорвано | Подождите автоматическое переподключение |

## Безопасность

- Пароль в открытом виде!!! Будьте внимательны
- Ограничьте доступ к порту 8787 файрволом
- Не запускайте от root без необходимости
