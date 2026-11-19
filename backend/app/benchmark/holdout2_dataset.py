"""Holdout 2: a second fresh set, written AFTER the advance-fee rules were added.

Never tune rules on it. It mixes scheme types the rules were built for (with new wording) and
types they were never built for (director-invoice fraud, state-compensation phishing,
"love" met in an app, lost-cargo fees) so that generalisation and its limits are both measured.
"""
import json
import os
import sys
from typing import Any, Dict, List

# (is_scam, category, language, amount, is_new_recipient, hour, freq_last_hour, text)
_ROWS = [
    # --- scams, RU ---
    (True, "fake_customs", "ru", 33000, True, 12, 1, "Пришло сообщение что мой груз из Китая арестован, чтобы вернуть его надо заплатить сбор через ссылку."),
    (True, "fake_prize", "ru", 45000, True, 11, 1, "Позвонили поздравить с розыгрышем смартфона, для отправки надо перевести комиссию."),
    (True, "fake_job", "ru", 52000, True, 10, 1, "Принимают на удалённую работу оператором, но надо оплатить комплект документов и обучение заранее."),
    (True, "fake_rental", "ru", 120000, True, 15, 1, "Сдаётся квартира за полцены, владелец за границей, просит внести бронь, пока не приеду."),
    (True, "romance", "ru", 400000, True, 21, 1, "Мужчина из Германии познакомился со мной в приложении, у него проблемы с таможней, помогаю деньгами."),
    (True, "ceo_invoice", "ru", 750000, True, 16, 1, "Директор написал в мессенджере с нового номера, просит срочно оплатить счёт поставщику, подробности пришлёт позже."),
    (True, "crypto", "ru", 300000, True, 19, 1, "Консультант показал кабинет, где моя криптовалюта растёт каждый день, нужно пополнить, чтобы вывести прибыль."),
    (True, "fake_relative", "ru", 500000, True, 14, 1, "Внучка звонит со слезами, говорит попала в полицию, адвокат просит деньги на залог, перевожу ему."),
    (True, "fake_prosecutor", "ru", 450000, True, 13, 1, "Мне позвонили, представились сотрудником прокуратуры, велели перевести деньги на страховой счёт для сохранности."),
    (True, "coached_masked", "ru", 350000, True, 14, 1, "Покупка стройматериалов для дачи."),
    # --- scams, KZ ---
    (True, "fake_customs", "kz", 35000, True, 12, 1, "Қытайдан келген жүгім ұсталды деп хабарлама келді, қайтару үшін алым төлеуім керек."),
    (True, "fake_prize", "kz", 48000, True, 11, 1, "Смартфон ұттың деп қоңырау шалды, жіберу үшін комиссия аударуды сұрады."),
    (True, "fake_job", "kz", 55000, True, 10, 1, "Қашықтан жұмысқа алам деп, құжаттар мен оқуға алдын ала төлем сұрады."),
    (True, "fake_rental", "kz", 110000, True, 15, 1, "Пәтер жартылай бағаға жалға берілді, иесі шетелде, келгенше бронь салуды сұрады."),
    (True, "romance", "kz", 390000, True, 21, 1, "Қолданбада танысқан шетелдік жігіт кедендегі мәселеге ақша сұрады."),
    (True, "ceo_invoice", "kz", 700000, True, 16, 1, "Директор жаңа нөмірден жазып, жеткізушіге шотты шұғыл төлеуді сұрады."),
    (True, "crypto", "kz", 280000, True, 19, 1, "Крипто кабинетінде пайдам өсіп жатыр деді, шығару үшін толықтыруым керек."),
    (True, "fake_relative", "kz", 480000, True, 14, 1, "Адвокат хабарласып, немерем полицияда екенін айтып, кепіл ақша аударуды сұрады."),
    (True, "phishing_compensation", "kz", 18000, True, 12, 1, "Мемлекеттен өтемақы тиесілі деген сілтеме келді, алу үшін картаны растап, аздап жарна төлеу керек."),
    (True, "coached_masked", "kz", 340000, True, 14, 1, "Саяжайға құрылыс материалдарын алу."),
    # --- legitimate, RU ---
    (False, "contractor", "ru", 650000, True, 12, 1, "Оплата счёта за ремонт офиса подрядчику по акту выполненных работ."),
    (False, "customs_legit", "ru", 480000, True, 11, 1, "Таможенная пошлина за ввоз автомобиля по декларации брокера."),
    (False, "fine", "ru", 15000, True, 10, 1, "Погашение штрафа ГИБДД через банк."),
    (False, "mortgage_help", "ru", 600000, False, 17, 1, "Перевожу дочери деньги на первый взнос по ипотеке, она сама попросила."),
    (False, "tickets", "ru", 180000, True, 13, 1, "Покупка билетов на самолёт в авиакомпании по бронированию."),
    (False, "dentist", "ru", 240000, True, 14, 1, "Оплата стоматолога, лечение по плану, договор подписан."),
    (False, "wedding_gift", "ru", 500000, False, 14, 1, "Подарок сыну на свадьбу."),
    (False, "furniture", "ru", 320000, True, 12, 1, "Предоплата за мебель по договору, фабрику видела лично."),
    (False, "family_asked", "ru", 130000, False, 18, 1, "Перевод родственнице на лечение, звонила вчера, попросила помочь, всё проверено."),
    (False, "utilities_night", "ru", 48000, False, 23, 1, "Оплата коммунальных услуг за три месяца."),
    # --- legitimate, KZ ---
    (False, "contractor", "kz", 640000, True, 12, 1, "Кеңсені жөндеген мердігерге орындалған жұмыс актісі бойынша төлем."),
    (False, "customs_legit", "kz", 470000, True, 11, 1, "Көлікті әкелгені үшін кеден баждарын декларация бойынша төлеу."),
    (False, "fine", "kz", 14000, True, 10, 1, "ЖИДТ айыппұлын банк арқылы төлеу."),
    (False, "mortgage_help", "kz", 580000, False, 17, 1, "Қызыма ипотеканың алғашқы жарнасына аударып жатырмын, өзі сұрады."),
    (False, "tickets", "kz", 170000, True, 13, 1, "Авиакомпаниядан ұшаққа билет брондау."),
    (False, "dentist", "kz", 230000, True, 14, 1, "Тіс емдеуге жоспар бойынша төлем, шарт жасалды."),
    (False, "wedding_gift", "kz", 520000, False, 14, 1, "Ұлыма үйлену тойына сыйлық."),
    (False, "furniture", "kz", 310000, True, 12, 1, "Жиһазды шарт бойынша алдын ала төлеу, фабриканы өзім көрдім."),
    (False, "family_asked", "kz", 120000, False, 18, 1, "Туысыма емделуге көмек, кеше хабарласып сұрады, бәрін тексердім."),
    (False, "utilities_night", "kz", 45000, False, 23, 1, "Үш айлық коммуналдық қызметтерге төлем."),
]


def build_holdout2() -> List[Dict[str, Any]]:  # Any: JSON scenario mapping
    out: List[Dict[str, Any]] = []
    for idx, (is_scam, cat, lang, amount, is_new, hour, freq, text) in enumerate(_ROWS, start=2001):
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
            "attack_vector": cat if is_scam else "benign_holdout2",
            "split": "holdout2",
        })
    return out


if __name__ == "__main__":
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scenarios_holdout2.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(build_holdout2(), f, ensure_ascii=False, indent=2)
    print(f"Wrote {len(_ROWS)} holdout2 scenarios -> {target}", file=sys.stderr)
