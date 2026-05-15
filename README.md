# SSH SOCKS Proxy

## Описание

SSH SOCKS Proxy — служба, которая создаёт постоянный SSH-туннель с динамическим пробросом портов (SOCKS5 прокси). Позволяет маршрутизировать трафик через удалённый SSH-сервер.

## Параметры

| Параметр | Описание | По умолчанию |
|----------|---------|--------------|
| `HOST` | Адрес SSH-сервера | `example.com` |
| `PORT` | Порт SSH-сервера | `22` |
| `USER` | Имя пользователя | `root` |
| `PASSWORD` | Пароль | `Passw0rd` |
| `PROXY_PORT` | Порт SOCKS-прокси | `8787` |
| `RECONNECT_DELAY` | Задержка переподключения (сек) | `5` |
| `LOG_FILE` | Путь к логу | `/opt/ssh_proxy/ssh-proxy.log` |

## Установка и запуск

### 1. Установка зависимостей

```bash
sudo apt install sshpass
```

### 2. Клонирование репозитория

```bash
sudo git clone https://github.com/Antowka/ssh_proxy.git /opt/ssh_proxy
sudo chmod +x /opt/ssh_proxy/ssh_proxy.py
```

### 3. Systemctl

```bash
sudo cp ssh-proxy.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ssh-proxy
```

### 4. Управление

```bash
sudo systemctl status ssh-proxy   # статус
sudo systemctl restart ssh-proxy  # перезапуск
sudo systemctl stop ssh-proxy    # остановка
sudo journalctl -u ssh-proxy -f   # логи
```

## Настройка

Отредактируйте `/opt/ssh_proxy/ssh_proxy.py` и измените параметры в начале файла (`HOST`, `PORT`, `USER`, `PASSWORD`, `PROXY_PORT`). После изменений перезапустите службу:

```bash
sudo systemctl restart ssh-proxy
```

## Использование

После запуска SOCKS-прокси доступен по адресу `http://127.0.0.1:8787` (или `0.0.0.0:8787` для внешнего доступа). Настройте браузер или приложение использовать SOCKS5 прокси с этим адресом.