# Mattermost-Redmine Integrations

![header.png](./imgs/header.png "Diagram project.")

* **Проект создан для интеграции сервиса mattermost и redmine.**
* **Данная версия поддерживает локальную и глобальную интеграцию.**

## Содержание
- [Преимущества](#преимущества)
- [Актуальность](#актуальность)
- [Команды](#команды)
- [Некоторое соглашение](#некоторое-соглашение)
- [Тестирование приложения](#тестирование-приложения)
- [Схема проекта](#схема-проекта)
- [Настраиваем среду разработки](#настраиваем-среду-разработки)
- [Установка redmine контейнера через docker-compose.yml](#установка-redmine-контейнера-через-docker-composeyml)
- [Установка mattermost контейнера через docker-compose.yml](#установка-mattermost-контейнера-через-docker-composeyml)
- [Установка интеграции Redmine и Mattermost](#установка-интеграции-redmine-и-mattermost)
- [Полезные docker команды](#полезные-docker-команды)
- [Автотесты](#автотесты)
- [Настройка Reverse Proxy для нашего приложения](#настройка-reverse-proxy-для-нашего-приложения)
- [Настройка HTTPS(зашифрованного соединения) для приложения](#настройка-httpsзашифрованного-соединения-для-приложения)
- [Для администратора](#для-администратора)
- [Используемые библиотеки](#используемые-библиотеки)
- [Полезные ссылки](#полезные-ссылки)
- [С какими столкнулся проблемами](#с-какими-столкнулся-проблемами)
- [Не по теме](#не-по-теме)

## Преимущества

* Автоматическое создание тикетов. Одним сообщением можно создать несколько тикетов.
* Мониторинг тикетов в redmine. Вы всегда можете одной командой посмотреть тикеты на себя, посмотреть
  созданные тикеты.
* Расширяемое приложение. Проект открыт для дальнейшей разработки, легко масштабируется.
  Например, при разработке, можно добавить объединение нескольких пользователей в группы, управление тикетами,
  уведомление на почту по определённым событиям, автоматическое создание нескольких проектов в одну строку, 
дальнейшая валидация полученных данных, перехват слов пользователя по регулярным выражениям и многое другое.
* Создание тикетов по форме Redmine прямо через приложение.
* Создание ссылок перенаправляющих в Redmine, а именно на тикеты, на проекты, на пользователей, на `Мои задачи`,
  на `Созданные задачи`.
* Максимальная валидация отправленных данных по тикетам и обработка ошибок.
* Настроено соответствие пользователей Mattermost и Redmine через файл `.docker.env.`
* Кнопка звонка в Яндекс Телемост

## Актуальность

> 💡 *В компании есть встречи, по результатам встречи раздаются поручения. Поручения теряются и не выполняются.*
> *Параллельно поручения живут в тикетах в багтрекере.*
> *Хочется, чтобы все поручения жили в багтрекере, там мониторились и выполнялись.*

## Команды
* За интеграцию отвечает самостоятельное приложение на python с библиотекой Flask в виде бота.

* Точка входа для интеграции `/redmine` *commands

| Команды       | Описание                                                                                |
|---------------|-----------------------------------------------------------------------------------------|
| /help         | Краткая справочная информация о приложении и его командах                               |
| /new_task     | Создать одну задачу в форме Redmine                                                     |
| /new_tasks    | Создать одну или несколько задач для одного или нескольких пользователей в одну команду |
| /tasks_by_me  | Показать задачи, которые я поручил другим                                               |
| /tasks_for_me | Показать поставленные мне задачи                                                        |


## Некоторое соглашение

+ Чтобы создать ссылку на тикет, напишите по следующему примеру `#t(ID тикета)`.
  Например, `#t10`. Вот один из примеров. ![screen9.png](./imgs/screen9.png "Example create link for tickets")

  При нажатии на ссылку, происходит перенаправление на конкретный тикет. 

  **Важное уточнение.** Перехватывающий веб сокет работает только с каналами, директом приложения и потоками. 
  Чтобы создать ссылки в виде `#t(ID тикета)` в директе, просто напишите сообщение боту, бот создаст ссылки в тексте. 
  Если вы пишете в канале или потоке, или в директе бота, то копировать текст не нужно.
  
  
  > ###### Mattermost API Reference
  > This is an example of making a user_typing request, with the purpose of alerting the server that the connected 
  > client has begun typing in a **channel** or **thread**.

  Для обработки ваших ссылок на тикеты в общедоступных и добавленных частных каналах требуется следующие действия.
  
  >#### https://developers.mattermost.com/integrate/reference/bot-accounts/#bot-account-creation
  ><br>
  > To add the bot account to teams and channels you want it to interact in, select the team drop-down menu, then select <br> 
  > Invite People. Next, select Invite Member and enter the bot account in the Add or Invite People field. Then select <br>
  > Invite Members. You should now be able to add the bot account to channels like any other user.<br>
  

+ Установка приложения и приглашение бота в команду
  https://drive.google.com/file/d/16RAOr7d5huqCDg7T4-Ww5wqewNmREY-n/view?usp=sharing


+ Для идентификации пользователя Redmine и Mattermost впишите пользовательский **(логин в redmine)=(логин в mattermost)** в `.docker.env`. Пример
  - **mattermost_username=redmine_username**
  - **seconad_username_in_mattermost=second_username_in_redmine**

  **Строго, сначала логин маттермоста=логин редмайна**

+ Преобразование текста тикета в ссылку требует прав администратора для приложения. Из документации
  > ### Create a ephemeral post <br>
  > Create a new ephemeral post in a channel.<br><br>
  > **Permissions**<br>
  > _Must have create_post_ephemeral permission **(currently only given to system admin)**_
  
+ Внимание, если маттермост не видит запущенное приложение, то необходимо
  - или в настройках администратора добавить возможность загрузки по хосту `127.0.0.1`(по умолчанию не разрешено)
  - или в файле `.env` изменить `EXTERNAL` хосты на `0.0.0.0`(для запуска через `flask run -h 0.0.0.0` или `gunicorn`)

## Тестирование приложения

1. Предустановить необходимые пакеты
2. Создать общую docker сеть
3. Установить докер контейнер redmine и запустить
4. Установить докер контейнер mattermost и запустить
5. После активации REST API на локальных сервисах добавить необходимые переменные окружения в файл
   `.env` приложения. Файл находится в `./wsgi/.env`
6. После добавления всех необходимых переменных в `./wsgi/.env` установить докер контейнер
   mattermost-redmine интеграции и запустить
7. Установить приложение в mattermost командой c параметрами хоста и порта виртуального окружения

   ```
   /apps install http http://host:port/manifest.json
   ```

8. Сгенерируйте токен для приложения через настройки
9. Добавьте токен в  `./wsgi/.env`
10. Добавьте токен администратора и дайте разрешение на создание постов. Для работы фичи t#ID необходимо установить 
бота в System Admin.
11. Добавьте всех необходимых пользователей **mattermost_login=redmine_login** в  `./wsgi/.env`, 
предварительно убедитесь что логины корректны и аккаунты активны.
12. Перезапустите докер контейнер в папке `./wsgi`
    ```shell
    docker compose stop
    docket compose up
    ```
13. Приложение готово

## Схема проекта

![diagram.svg](./imgs/diagram.svg "Diagram project.")

## Настраиваем среду разработки

* Подробную информацию по первичной настройке можно посмотреть по ссылке
  https://developers.mattermost.com/integrate/apps/quickstart/quick-start-python/


* Первым делом удаляю старую версию docker и устанавливаю новую
  https://docs.docker.com/engine/install/ubuntu/


* копируем ./wsgi/.env.example в ./wsgi/.env
  ```shell
  cp ./wsgi/.env.example ./wsgi/.env
  ```

## Установка redmine контейнера через docker-compose.yml

* Для начала, создайте папку docker для работы с контейнером
    ```bash
    mkdir ./rm
    cd ./rm
    ```
* Cтавлю redmine контейнер. Образ подходит для разработки и производства https://github.com/sameersbn/docker-redmine.git
    + **Вам нужно самостоятельно настроить ваш образ в зависимости от ваших предпочтений**

* переходим на сайт с логином admin и паролем admin, меняем пароль, далее `Администрирование` > `Настройки`
    + Раздел `Аутентификация` - Да
    + Раздел `API` - Подключаем REST
      ![screen1.png](./imgs/screen1.png "Redmine activate API")


## Установка mattermost контейнера через docker-compose.yml

Детали установки контейнера и приложения можно посмотреть тут
https://developers.mattermost.com/integrate/apps/quickstart/quick-start-python/

Но мы будем использовать образ, который поддерживает гибкую настройку https://github.com/mattermost/docker.git
    + **Вам нужно самостоятельно настроить ваш образ в зависимости от ваших предпочтений**
    + В этой версии не настроена поддержа plugin_app, поэтому следуют расширить параметры из 
      https://developers.mattermost.com/integrate/apps/quickstart/quick-start-python/


* mattermost контейнер запущен
  ![screen2.png](./imgs/screen2.png "Home page for loging")

* нам нужно сгенерировать токен админа для REST API запросов и добавить в `./wsgi/.env`.
  ![screen3.png](./imgs/screen3.png "Generate access admin token")

## Установка интеграции Redmine и Mattermost

* переходим в директорию ./wsgi и запускаем последний контейнер с ботом-приложением.
    ```shell
      docker compose up
    ```

* давайте удостоверимся, что приложение действительно работает и может пинговаться с другими docker контейнерами
  ```shell
  docker exec -it conteiner_name_app bash
  curl -I http://host_redmine:port_redmine/
  ```
  > HTTP/1.1 200 OK
  ```shell
  curl -I http://host_mattermost:port_mattermost/
  ```
  > HTTP/1.1 405 Method Not Allowed

  curl команды
  - `GET` curl -I http://localhost:5000/*endpoint
  - `POST` curl --header "Content-Type: application/json"   --request POST   --data '{"item1":"data1","item2":"data2"}' 
     http://127.0.0.1:5000/*endpoint
  

* Чтобы установить приложение, нужно перейти на ваш запущенный mattermost сайт и ввести `/`(slash) команду по примеру из
  официальной документации. https://developers.mattermost.com/integrate/apps/quickstart/quick-start-python/
  > #### Install the App on Mattermost
  > `/apps install http http://mattermost-apps-python-hello-world:8090/manifest.json`

  В моем случае, я добавил команду `/apps install http http://external_ip_address:8090/manifest.json`
* Если вам нужно удалить его, то смотрим здесь
  https://developers.mattermost.com/integrate/apps/quickstart/quick-start-python/#uninstall-the-app
* После успешной загрузки нужно сгенерировать токен для приложения, добавить его в `./wsgi/.env`
  Сгенерировать токен нужно в разделе `Интеграции` > `Аккаунты ботов` > `@redmine`.
  Также предоставьте доступ бота к Direct сообщениям, назначьте ему роль администратор так как интеграция работает 
через личные сообщения. Интеграция работает c API токеном.
  ![screen4.png](./imgs/screen4.png "Generate access app token and get privilege.")


* Теперь приложение будет:
    - создавать тикеты
    - создавать тикет по форме Redmine
    - показывать тикеты, которые поручены вам
    - показывать тикеты, которые вы назначили
    - обрабатывать ошибки при отсутствии вас как пользователя на платформе redmine или отсутствии необходимых токенов,
      или
      при вводе невалидной информации.
    - Создавать ссылки перенаправляющие в redmine

## Полезные docker команды

- docker compose up - _Create and start containers_ 
- docker compose down -  _Stop and remove containers, networks_ 

[docker compose commands](https://docs.docker.com/compose/reference/)


## Автотесты

- мы тестируем только клиентскую часть
- предварительно необходимо запустить докер контейнеры redmine и mattermost
- создайте файл `.test.env` и добавьте необходимые переменные для тестирования
  Пример
  ```text
  APP_SCHEMA=http
  APP_HOST_INTERNAl=127.0.0.1
  APP_PORT_INTERNAL=8090
  APP_HOST_EXTERNAL=127.0.0.1
  APP_PORT_EXTERNAL=8090
  
  MM_SCHEMA=http
  MM_HOST_EXTERNAL=127.0.0.1
  MM_PORT_EXTERNAL=8065
  
  RM_SCHEMA=http
  RM_HOST_EXTERNAL=127.0.0.1
  RM_PORT_EXTERNAL=3000
  
  rm_admin_key=redmine_secret
  mm_app_token=app_secret
  
  app_url_internal=${APP_SCHEMA}://${APP_HOST_INTERNAl}:${APP_PORT_INTERNAL}
  app_url_external=${APP_SCHEMA}://${APP_HOST_EXTERNAL}:${APP_PORT_EXTERNAL}
  
  redmine_url_external=${RM_SCHEMA}://${RM_HOST_EXTERNAL}:${RM_PORT_EXTERNAL}
  mattermost_url_external=${MM_SCHEMA}://${MM_HOST_EXTERNAL}:${MM_PORT_EXTERNAL}
  
  # testing mattermost client
  test_mm_email1=t1@mail
  test_mm_username1=t1
  test_mm_password1=super_secret
  test_mm_first_name1=TestMattermost
  test_mm_last_name1=UserMattermost
  
  test_mm_email2=t2@mail
  test_mm_username2=t2
  test_mm_password2=super_secret
  test_mm_first_name2=TestMattermost2
  test_mm_last_name2=UserMattermost2
  
  # redmine clients
  test_rm_email1=t1@mail.ru
  test_rm_username1=test.user1
  test_rm_password1=super_secret
  test_rm_first_name1=Test1
  test_rm_last_name1=User1
  
  test_rm_email2=t2@mail.ru
  test_rm_username2=test.user2
  test_rm_password2=super_secret
  test_rm_first_name2=Test2
  test_rm_last_name2=User2
  
  # usernames mattermost with redmine account
  # For example:
  # mattermost_username=redmine_username
  # seconad_username_in_mattermost=second_username_in_redmine
  # and etc...
  
  t1=test.user1
  t2=test.user2
  ```
- запускаем тесты и смотрим покрытие кода
  ```bash
  coverage run -m pytest
  ```
  
  ```bash
  coverage report 
  ```  

  ```text
  Name                          Stmts   Miss  Cover
  -------------------------------------------------
  ext_funcs.py                      9      0   100%
  tests/__init__.py                 0      0   100%
  tests/blocks_code/blocks.py      30      0   100%
  tests/conftest.py                37      3    92%
  tests/test_app.py               306      0   100%
  wsgi/__init__.py                401     31    92%
  wsgi/client_errors.py             6      0   100%
  wsgi/constants.py                 2      0   100%
  wsgi/decorators.py               29      3    90%
  wsgi/my_bot.py                   27      2    93%
  wsgi/redmine_api.py              48      0   100%
  wsgi/settings.py                 60      2    97%
  wsgi/views.py                    26      2    92%
  -------------------------------------------------
  TOTAL                           981     43    96%
  ```



### Информация о приложении `help`

![screen8.png](./imgs/screen8.png "Help info.")

### Создать задания `new_tasks`

![screen5.png](./imgs/screen5.png "Create tickets.")

### Посмотреть задания назначенные мне `tasks_for_me`

![screen6.png](./imgs/screen6.png "Look ticket for me.")

### Посмотреть задания назначенные мною `tasks_by_me`

![screen7.png](./imgs/screen7.png "Look my tickets.")

### Создать тикет по форме Redmine `new_task`

![screen10.png](./imgs/screen10.png "form for ticket")

## Настройка Reverse Proxy для нашего приложения
  
- прописываем конфигурацию nginx
  * установка nginx на сервер
  ```shell
  sudo apt update
  sudo apt install nginx
  ```
  * запустить службу nginx
  ```shell
  sudo systemctl start nginx
  ```
  * создаём новый файл конфигурации
  ```shell
  sudo cp ./wsgi/app_nginx /etc/nginx/sites-enabled/app_nginx
  ```
  
  * обновите службу nginx
  ```shell
  sudo systemctl reload nginx
  ```
 
## Настройка HTTPS(зашифрованного соединения) для приложения

* Устанавливаем certbot на сервер, https://certbot.eff.org/
* Следуем по инструкции по установке и настройке, certbot всё делает за вас
  
## Для администратора

Как добавить интеграцию у себя на сервере?

1. Предварительно у вас должны быть необходимые пакеты упомянутые выше
2. клонировать https://github.com/ArtemIsmagilov/redmine-mattermost-integrations.git и перейти в папку wsgi/
3. копировать .docker.env.exampple в .docker.env в текущей директории и заменить необходимые параметры
4. копировать app_nginx в /etc/nginx/sites-enables/ рядом в default ссылкой, заменить необходимые параметры
(порты, пути к сертификатам). Для тестирования используется конфигурация http, 
для использования в производстве используется https
5. измените параметры gunicorn.conf.py(accesslog*=имя файла, loglevel='error', количество воркеров, путь к сертификатам)
6. запустите докер контейнер
7. установить приложение командой в mattermost /apps install http ...
8. создайте токен для бота, предоставьте права для REST API операций. Добавьте бота в команду как пользователя - требуется для работы с websocket [Subscriptions](https://developers.mattermost.com/integrate/apps/functionality/subscriptions/)
   > ### Note:
   > #### Bots need to join a channel before subscribing to that channel’s events. Similarly, bots need to join a team before subscribing to that team’s events.
10. добавьте токен, необходимых пользователей в .docker.env и заново запустите docker контейнер

## Используемые библиотеки

* `mattermostautodriver`.
    - Github https://github.com/embl-bio-it/python-mattermost-autodriver
    - Документация https://embl-bio-it.github.io/python-mattermost-autodriver
* `python-redmine`.
    - Github https://github.com/maxtepkeev/python-redmine
    - Документация https://python-redmine.com

## Полезные ссылки

* REST API redmine - https://www.redmine.org/projects/redmine/wiki/Developer_Guide
* Простое приложение `hello world` в mattermost на python -
  https://developers.mattermost.com/integrate/apps/quickstart/quick-start-python/
* REST API mattermost - https://api.mattermost.com/
* matterbridge https://github.com/42wim/matterbridge
* Mattermost chat plugin for Redmine - https://github.com/altsol/redmine_mattermost
* Docker image Redmine - https://hub.docker.com/_/redmine
* Установка redmine через
  docker-compose - https://kurazhov.ru/install-redmine-on-docker-compose/?ysclid=lhu5e6s0bb161225177
* Чат-бот для mattermost - https://habr.com/ru/companies/hh/articles/727246/
* Документация по докеру - https://docs.docker.com/engine/install/
* HTTPS на Flask - https://blog.miguelgrinberg.com/post/running-your-flask-application-over-https
* Прокси приложения - https://dvmn.org/encyclopedia/web-server/deploy-django-nginx-gunicorn/
* Документация Gunicorn - https://docs.gunicorn.org/en/latest/install.html
* Redmine docker в production - https://github.com/sameersbn/docker-redmine.git
* Mattermost docker в production - https://github.com/mattermost/docker.git

## С какими столкнулся проблемами
- Неинформативные сообщения от mattermost(а), при установке последней версии докер образа не работал websocket
через форумы узнал, что последная версия требует проксирования, даже при локальной разработке
- Нет никакой информации (крайне мало) по работе с websocket. Через websocket удобнее всего разрабатывать автоматизацию
так как не требуются формы. Важно лишь указать соглашение по взаимодействию
- Не работал Websocket на стабильной версии после установки. Выяснилось, websocket работает только по добавленным каналам.
Для совместимости, установил версию mattermost как у заказчика _7.7.1_
- python:latest версия докер контейнера весит около 1 GB, пробую загружать образ python:slim. Версия slim
быстрее запускается, меньше весит(только необходимые пакеты), но иногда нестабильно работает (может выдавать разные 
статусы ошибок при возникновении запланированных исключениях в python)
- После установки плагина, бот не добавлялся в канал, по крайней мере визуально сразу не понять что он появился сразу.
Для этого можно добавить его в директ или добавить в команду как пользователя. Если добавить как пользователя
его можно добавлять в различные каналы, чего мы и хотим https://forum.mattermost.com/t/add-a-bot-to-channels/8355/15

## Дополнительные работы

- Рефакторинг кода
- Добавить русский язык

## Не по теме

Если вам надоел перегрев ноутбука при работе в Oracle VirtualBox, то одно первых решений - отключить запись логов.
По крайней мере, у меня энергопотребление снизилось с **Очень высокого** до **Высокого**, иногда **Умеренный**.
Исключение, если вы что-то мониторите.

**Отключение логов** 
- https://www.virtualbox.org/ticket/11988
- https://ubuntuforums.org/showthread.php?t=879256
- Выбираем папку C:\Users\user\VirtualBox VMs\Ubuntu\Logs правой кнопкой мыши -> `Безопасность` -> `Изменить` -> Выбираем нашего пользователя от которого устанавливался VBox -> Ставим галочку `Запретить запись` -> `Применить`. Теперь запись логов будет не доступна. Это освободит процессор и память от лишней работы.
  
