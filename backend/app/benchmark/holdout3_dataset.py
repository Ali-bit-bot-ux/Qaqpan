"""Holdout 3: the final honest set, written AFTER the friction fixes and never tuned on.

Mix is closer to real traffic than holdout 1/2: 25 scams and 45 legitimate transfers, most of the
legitimate ones everyday (small, known recipients) with a realistic share of large or new-recipient
payments. It also includes scam types the rules were not built for (insurance refund, collectors,
QR phishing, fake tech support, fake charity, boss-asks-for-advance, coached masked answers) so the
limits stay visible. Evaluate it, report it, and do not change rules to improve its numbers.
"""
import json
import os
import sys
from typing import Any, Dict, List

# (is_scam, category, language, amount, is_new_recipient, hour, freq_last_hour, text)
_ROWS = [
    # --- scams, RU ---
    (True, "insurance_refund", "ru", 24000, True, 13, 1, "Позвонили из страховой, сказали что мне положен возврат за полис, нужно оплатить комиссию за перевод выплаты."),
    (True, "fake_bank_code", "ru", 380000, True, 16, 1, "Сотрудник банка попросил назвать код из смс и перевести деньги на защищённый счёт для отмены чужой операции."),
    (True, "marketplace_phishing", "ru", 18000, True, 12, 1, "Покупатель на маркетплейсе просит перейти в мессенджер и оплатить доставку по ссылке, которую прислал."),
    (True, "investment_club", "ru", 500000, True, 19, 1, "Знакомый пригласил в закрытый инвестиционный клуб, обещают тридцать процентов в месяц, вношу первый взнос."),
    (True, "fake_lawyer", "ru", 450000, True, 15, 1, "Мне сообщили, что на мою карту оформили заём мошенники, юрист предлагает перевести деньги на специальный счёт для проверки."),
    (True, "fake_rental", "ru", 90000, True, 14, 1, "Хозяйка квартиры в другом городе просит перевести задаток, ключи отправит курьером после оплаты."),
    (True, "grandchild_police", "ru", 550000, True, 17, 1, "Внук звонит, плачет, говорит что в полиции, просит срочно перевести деньги адвокату, пока не узнали родители."),
    (True, "fake_charity", "ru", 60000, True, 18, 1, "Меня попросили помочь больному ребёнку, фонд прислал реквизиты в мессенджере, перевожу, говорят счёт идёт на операцию."),
    (True, "boss_advance", "ru", 650000, True, 11, 1, "Начальник написал с нового номера, просит срочно перевести аванс подрядчику, говорит что в командировке и позвонить не может."),
    (True, "debt_collector", "ru", 270000, True, 12, 1, "Звонили из коллекторского агентства, сказали что у меня долг за мужа, надо оплатить сегодня иначе приедут и опишут имущество."),
    (True, "qr_phishing", "ru", 35000, True, 20, 1, "Мне прислали QR-код для получения возврата за товар, по нему я ввела данные карты и теперь нужно подтвердить перевод."),
    (True, "fake_tech_support", "ru", 140000, True, 21, 1, "Мастер по компьютерам удалённо подключился, сказал что вирус, надо перевести деньги на защищённый кошелёк, чтобы спасти данные."),
    (True, "coached_masked", "ru", 400000, True, 14, 1, "Оплата за курсы вождения."),
    # --- scams, KZ ---
    (True, "insurance_refund", "kz", 26000, True, 13, 1, "Сақтандыру компаниясынан хабарласып, төлем қайтарылады деп, аудару комиссиясын төлеуді сұрады."),
    (True, "fake_bank_code", "kz", 360000, True, 16, 1, "Банк қызметкері смс-кодты айтуды және қауіпсіз шотқа аударуды сұрады."),
    (True, "marketplace_phishing", "kz", 17000, True, 12, 1, "Маркетплейстегі сатып алушы мессенджерге өтіп, жеткізуді сілтеме арқылы төлеуді сұрады."),
    (True, "investment_club", "kz", 480000, True, 19, 1, "Таныс адам жабық инвестициялық клубқа шақырып, айына отыз пайыз уәде етті, алғашқы жарнаны салып жатырмын."),
    (True, "fake_rental", "kz", 85000, True, 14, 1, "Пәтер иесі басқа қалада тұрады, кілтті курьермен жібереді деп, залог аударуды сұрады."),
    (True, "grandchild_police", "kz", 520000, True, 17, 1, "Немерем жылап қоңырау шалып, полицияда екенін айтып, ата-анасы білмей тұрғанда заңгерге ақша аударуды сұрады."),
    (True, "fake_charity", "kz", 55000, True, 18, 1, "Ауру балаға көмек деп қор мессенджерге реквизит жіберді, операцияға жиналып жатыр дейді."),
    (True, "boss_advance", "kz", 620000, True, 11, 1, "Бастық жаңа нөмірден жазып, іссапарда екенін, подрядчикке аванс шұғыл аударуды сұрады."),
    (True, "debt_collector", "kz", 260000, True, 12, 1, "Коллекторлық агенттіктен қоңырау шалып, күйеуімнің қарызын бүгін төлемесем мүлікті сипаттаймыз деді."),
    (True, "qr_phishing", "kz", 32000, True, 20, 1, "Қайтарым алу үшін QR-код келді, карта деректерін енгіздім, енді аударымды растауым керек."),
    (True, "fake_tech_support", "kz", 130000, True, 21, 1, "Компьютер шебері қашықтан қосылып, вирус бар деп, деректі құтқару үшін қорғалған әмиянға аударуды айтты."),
    (True, "coached_masked", "kz", 380000, True, 14, 1, "Жүргізу курсына төлем."),
    # --- legitimate, RU ---
    (False, "internet", "ru", 5500, False, 9, 1, "Оплата интернета за месяц."),
    (False, "family_fuel", "ru", 12000, False, 18, 1, "Перевод на карту мужа, ему на бензин."),
    (False, "farmer", "ru", 18000, True, 11, 1, "Купила продукты у фермера по договоренности."),
    (False, "tutor", "ru", 24000, False, 17, 1, "Перевод репетитору за занятия по математике."),
    (False, "cinema", "ru", 6000, True, 20, 1, "За билеты в кино на всю семью."),
    (False, "taxi_night", "ru", 3500, True, 1, 1, "Оплата такси за поездку из аэропорта."),
    (False, "friend_debt", "ru", 9000, True, 19, 1, "Возвращаю долг подруге за ресторан."),
    (False, "rent", "ru", 150000, False, 10, 1, "Аренда квартиры за месяц хозяйке."),
    (False, "kindergarten", "ru", 42000, False, 9, 1, "Оплата детского сада и кружков."),
    (False, "savings", "ru", 100000, False, 15, 1, "Пополнение накопительного счёта."),
    (False, "credit_card", "ru", 85000, False, 12, 1, "Взнос по кредитной карте."),
    (False, "roof_repair", "ru", 480000, True, 13, 1, "Ремонт крыши по договору с бригадой."),
    (False, "washing_machine", "ru", 220000, True, 14, 1, "Покупка стиральной машины в магазине."),
    (False, "notary", "ru", 120000, True, 12, 1, "Оплата услуг нотариуса при покупке квартиры."),
    (False, "gift", "ru", 30000, True, 16, 1, "Подарок племяннику на день рождения."),
    (False, "tour", "ru", 580000, True, 11, 1, "Оплата туристической путёвки по договору."),
    (False, "office_rent", "ru", 300000, False, 10, 1, "Взнос за аренду офиса по договору."),
    (False, "clinic", "ru", 350000, False, 14, 1, "Лечение мамы в частной клинике по счёту."),
    (False, "study_abroad", "ru", 200000, False, 19, 1, "Перевод сыну на учёбу за границей, он просил."),
    (False, "translator", "ru", 45000, True, 15, 1, "Оплата услуг переводчика по документам."),
    (False, "hall_deposit", "ru", 160000, True, 12, 1, "Депозит за аренду зала на юбилей по договору."),
    (False, "parking_fine", "ru", 8000, True, 21, 1, "Заплатила штраф за парковку."),
    (False, "utilities_night", "ru", 60000, False, 23, 1, "Коммуналка за квартал."),
    # --- legitimate, KZ ---
    (False, "internet", "kz", 5500, False, 9, 1, "Айлық интернет ақысы."),
    (False, "family_fuel", "kz", 12000, False, 18, 1, "Күйеуімнің картасына жанармайға аударым."),
    (False, "farmer", "kz", 18000, True, 11, 1, "Фермерден азық-түлік алдым, келісім бойынша."),
    (False, "tutor", "kz", 24000, False, 17, 1, "Математикадан репетиторға сабақ ақысы."),
    (False, "cinema", "kz", 6000, True, 20, 1, "Бүкіл отбасына кинобилет үшін."),
    (False, "taxi_night", "kz", 3500, True, 1, 1, "Әуежайдан келген такси ақысы."),
    (False, "friend_debt", "kz", 9000, True, 19, 1, "Құрбыма мейрамхана үшін қарызымды қайтарып жатырмын."),
    (False, "rent", "kz", 150000, False, 10, 1, "Пәтер жалдау ақысы айына иесіне."),
    (False, "kindergarten", "kz", 42000, False, 9, 1, "Балабақша мен үйірме ақысы."),
    (False, "savings", "kz", 100000, False, 15, 1, "Жинақ шотын толықтыру."),
    (False, "credit_card", "kz", 85000, False, 12, 1, "Несие картасының жарнасы."),
    (False, "roof_repair", "kz", 470000, True, 13, 1, "Төбені жөндеуге бригадамен шарт бойынша."),
    (False, "washing_machine", "kz", 210000, True, 14, 1, "Дүкеннен кір жуғыш машина сатып алу."),
    (False, "notary", "kz", 115000, True, 12, 1, "Пәтер сатып алғанда нотариус қызметіне төлем."),
    (False, "gift", "kz", 30000, True, 16, 1, "Жиеніме туған күніне сыйлық."),
    (False, "tour", "kz", 570000, True, 11, 1, "Туристік жолдаманы шарт бойынша төлеу."),
    (False, "office_rent", "kz", 300000, False, 10, 1, "Кеңсе жалдау жарнасы шарт бойынша."),
    (False, "clinic", "kz", 340000, False, 14, 1, "Анамды жеке клиникада емдеуге шот бойынша."),
    (False, "study_abroad", "kz", 190000, False, 19, 1, "Ұлыма шетелде оқуына, ол өзі сұраған."),
    (False, "translator", "kz", 45000, True, 15, 1, "Құжаттарды аударатын маманның қызметі."),
    (False, "hall_deposit", "kz", 150000, True, 12, 1, "Мерейтойға залды алдын ала брондау шарт бойынша."),
    (False, "parking_fine", "kz", 8000, True, 21, 1, "Тұрақ үшін айыппұл төледім."),
]


def build_holdout3() -> List[Dict[str, Any]]:  # Any: JSON scenario mapping
    out: List[Dict[str, Any]] = []
    for idx, (is_scam, cat, lang, amount, is_new, hour, freq, text) in enumerate(_ROWS, start=3001):
        out.append({
            "id": idx,
            "is_scam": is_scam,
            "category": cat,
            "language": lang,
            "amount": float(amount),
            "is_new_recipient": is_new,
            "transfer_hour": hour,
            "frequency_last_hour": freq,
            "answer_text": text,
            "attack_vector": cat if is_scam else "benign_holdout3",
            "split": "holdout3",
        })
    return out


if __name__ == "__main__":
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios_holdout3.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(build_holdout3(), f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(_ROWS)} holdout3 scenarios -> {target}", file=sys.stderr)
