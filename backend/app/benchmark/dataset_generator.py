"""
Dataset Generator: Synthetic scenario generator for anti-fraud rules
and adversarial testing benchmark ('Fraudster Robot').
Supports Phase 1 (100 scenarios) and Phase 3 (300+ scenarios) in Russian and Kazakh.
"""

import json
import os
import random
from typing import List, Dict, Any  # Any: Scenario data items with mixed types

# Base seed for deterministic generation
random.seed(42)

# Templates for expanding realistic scams
SCAM_TEMPLATES_RU = [
    ("safe_account", "Следователь {rank} сказал срочно перевести {amount} на безопасный счет.", 450000),
    ("safe_account", "Служба безопасности ЦентрКредит велела отправить деньги на резервный счет для защиты.", 650000),
    ("safe_account", "Сотрудник нацбанка диктует реквизиты специального страхового счета.", 380000),
    ("safe_account", "Звонили из финмониторинга, сказали временно перекинуть на безопасную ячейку.", 520000),
    ("authority_pressure", "Капитан полиции {name} приказал выполнить перевод, иначе уголовное дело.", 300000),
    ("authority_pressure", "Звонил прокурор, сказал если не переведу деньги, арестуют все счета сегодня.", 420000),
    ("authority_pressure", "Сотрудник КНБ ведет секретную операцию и требует отправить средства.", 890000),
    ("authority_pressure", "Служба безопасности банка звонит по видеосвязи и требует подтвердить перевод.", 270000),
    ("family_accident", "Сын сбил человека на переходе, следователь требует деньги, чтобы не посадить.", 600000),
    ("family_accident", "Внук позвонил в слезах, сказал попал в ДТП, срочно нужны деньги врачу.", 450000),
    ("family_accident", "Дочь в реанимации после аварии, неизвестный мужчина требует срочный перевод.", 750000),
    ("family_accident", "Племянник задержан с наркотиками, полицейский просит выкуп прямо сейчас.", 500000),
    ("smurfing", "Следователь велел переводить частями по {amount} тенге, чтобы система банка не заблокировала.", 95000),
    ("smurfing", "Майор сказал разбить сумму на переводы по {amount} тенге на разные карты.", 85000),
    ("smurfing", "Перевожу третью часть по {amount} на резервный счет по инструкции оператора.", 90000),
    ("smurfing", "Сказали слать до 100 тысяч чтобы обойти проверку безопасности банка.", 99000),
    ("masking", "Мне сказали в банке говорить что это на ремонт, а сам перевожу по указке следователя.", 400000),
    ("masking", "Звонивший велел соврать что родственникам, а на самом деле спасаю счет.", 350000),
    ("fake_investment", "Аналитик платформы ГазпромИнвест велел пополнить брокерский счет через эту карту.", 450000),
    ("fake_investment", "Криптоброкер обещал утроить вклад к вечеру, перевожу стартовый депозит.", 250000),
]

SCAM_TEMPLATES_KZ = [
    ("safe_account", "Маған полициядан қоңырау шалды, шұғыл қауіпсіз шотқа {amount} теңге аудару керек дейді.", 500000),
    ("safe_account", "Банктің қауіпсіздік қызметі ақшаны сақтап қалу үшін резервтік шотқа салуды тапсырды.", 620000),
    ("safe_account", "Ұлттық банктен хабарласып, арнайы қорғалған шотқа қаражатты аударыңыз деді.", 430000),
    ("safe_account", "Тергеуші шұғыл сақтау шотына аударыңыз деді, әйтпесе ақша жоғалады.", 710000),
    ("authority_pressure", "ҰҚК қызметкері жедел операция өтіп жатыр деп ақшаны аударуға бұйрық берді.", 900000),
    ("authority_pressure", "Қаржы полициясы қылмыстық іс қозғалды деп шұғыл төлем жасауды талап етті.", 380000),
    ("authority_pressure", "Полиция капитаны қазір ақша аудармасаң үйіңіз тәркіленеді деп қорқытты.", 550000),
    ("authority_pressure", "Заң орындарынан қоңырау шалып, шоттарыңызды бұғаттаймыз деп қысым көрсетті.", 470000),
    ("family_accident", "Балам жол апатына түсті, тергеуші ақшаны қазір жібермесеңіз қамалады деп қорқытты.", 700000),
    ("family_accident", "Немерем жылап қоңырау соқты, ауруханаға шұғыл дәрігерге төлеу керек екен.", 350000),
    ("family_accident", "Қызым полиция бөлімінде отыр, ешкімге айтпай тез арада мына шотқа ақша сал деді.", 480000),
    ("family_accident", "Інім адам қағып кетті, қылмыстық істі жабу үшін мына кісіге ақша беру керек.", 600000),
    ("smurfing", "Қауіпсіздік қызметкері ақшаны бөліп-бөліп {amount} мыңнан жібер деп нұсқау берді.", 90000),
    ("smurfing", "Тергеуші банкті алдау үшін 100 мыңнан аз қылып {amount} теңгеден аудар деді.", 85000),
    ("smurfing", "Банк тексерісінен өту үшін бөліп {amount} теңгеден резервке аударамын.", 95000),
    ("masking", "Телефондағы адам банк сұраса туысыма деп айт деді, негізі шотымды сақтау үшін.", 450000),
    ("fake_investment", "Инвестициялық менеджер жеке картаға ақша салсаңыз жоғары пайыз болады деді.", 320000),
    ("fake_investment", "Криптовалютадан пайда түсіру үшін брокер мына шотқа депозит салуды сұрады.", 400000),
]

LEGIT_TEMPLATES_RU = [
    ("gift_family", "Внуку на день рождения на подарок, обещал отправить сегодня.", 30000),
    ("gift_family", "Дочке на карманные расходы во время учебы в университете.", 20000),
    ("gift_family", "Сестре на свадьбу подарок от всей нашей семьи.", 50000),
    ("gift_family", "Маме на покупку лекарств и продуктов на неделю.", 25000),
    ("rent_utilities", "Оплата аренды квартиры за ноябрь месяц хозяйке Гульнаре.", 180000),
    ("rent_utilities", "Коммунальные услуги и отопление за двухкомнатную квартиру.", 35000),
    ("rent_utilities", "Аренда парковочного места в подземном паркинге.", 25000),
    ("marketplace", "Покупка детской коляски на OLX, продавец отправит таксистом.", 45000),
    ("marketplace", "Купил зимнюю резину б/у у соседа по гаражному кооперативу.", 70000),
    ("marketplace", "Заказ домашней выпечки и торта на юбилей через инстаграм.", 18000),
    ("education", "Оплата курсов английского языка за второй модуль.", 60000),
    ("education", "Оплата детского сада за ребенка за ноябрь месяц.", 40000),
    ("medical", "Оплата услуг стоматолога за лечение и пломбирование зуба.", 35000),
    ("repair", "Оплата мастеру Ерлану за замену смесителя и труб в ванной.", 30000),
    ("car_service", "Замена моторного масла и фильтров на СТО у мастера.", 25000),
    ("debt_repayment", "Возврат долга коллеге за совместную покупку билетов.", 40000),
    ("groceries", "Скинулись с коллегами на пиццу и обед в офисе.", 8000),
]

LEGIT_TEMPLATES_KZ = [
    ("gift_family", "Немереме туған күніне сыйлыққа, құттықтап жіберіп жатырмын.", 30000),
    ("gift_family", "Қызыма колледждегі күнделікті жолақысы мен тамағына.", 20000),
    ("gift_family", "Қарындасымның ұзату тойына туыстар атынан шашу.", 50000),
    ("gift_family", "Анамның дәрі-дәрмегіне және азық-түлігіне жәрдем.", 25000),
    ("rent_utilities", "Пәтерақы қараша айына, пәтер иесі Айнұрға төлеу.", 190000),
    ("rent_utilities", "Үйдің коммуналдық қызметтері мен жылу ақысына.", 32000),
    ("marketplace", "OLX-тан пайдаланылған балалар арбасын сатып алдым.", 45000),
    ("marketplace", "Көршіден көліктің қысқы дөңгелегін сатып алғанға төлем.", 65000),
    ("marketplace", "Инстаграм арқылы мерекелік тортқа тапсырыс бергенге.", 20000),
    ("education", "Баланың мектепке дейінгі дайындық курсына айлық төлем.", 35000),
    ("education", "Ағылшын тілі үйірмесіне кезекті төлемақы.", 40000),
    ("medical", "Тіс емханасына тіс емдеткені үшін каспи арқылы төлеу.", 30000),
    ("repair", "Үйдің су құбырын жөндеген шебер Қайратқа төлем.", 25000),
    ("car_service", "СТО-да көліктің майы мен тежегішін ауыстырғанға.", 35000),
    ("debt_repayment", "Әріптесіме түскі асқа берген қарызымды қайтарып жатырмын.", 15000),
]


def generate_full_dataset(target_count: int = 320) -> List[Dict[str, Any]]:  # Any: Scenario items
    """Generates an extended dataset of balanced scam and legit scenarios."""
    scenarios: List[Dict[str, Any]] = []  # Any: Scenario data items
    current_id = 1
    half_count = target_count // 2  # 160 scam, 160 legit

    ranks = ["майор", "капитан", "лейтенант", "полковник"]
    names = ["Иванов", "Ахметов", "Смагулов", "Ким"]

    # 1. Generate 160 Scam Scenarios
    scam_count = 0
    while scam_count < half_count:
        if scam_count % 2 == 0:
            cat, tmpl, base_amt = random.choice(SCAM_TEMPLATES_RU)
            lang = "ru"
            amt = base_amt + random.randint(-15000, 35000)
            text = tmpl.replace("{rank}", random.choice(ranks))
            text = text.replace("{name}", random.choice(names))
            text = text.replace("{amount}", f"{amt:,}")
        else:
            cat, tmpl, base_amt = random.choice(SCAM_TEMPLATES_KZ)
            lang = "kz"
            amt = base_amt + random.randint(-15000, 35000)
            text = tmpl.replace("{amount}", f"{amt:,}")

        scenarios.append({
            "id": current_id,
            "is_scam": True,
            "category": cat,
            "language": lang,
            "amount": amt,
            "is_new_recipient": True,
            "answer_text": text,
            "expected_risk": "HIGH"
        })
        current_id += 1
        scam_count += 1

    # 2. Generate 160 Legit Scenarios
    legit_count = 0
    while legit_count < half_count:
        if legit_count % 2 == 0:
            cat, tmpl, base_amt = random.choice(LEGIT_TEMPLATES_RU)
            lang = "ru"
            amt = base_amt + random.randint(-5000, 10000)
            text = tmpl
            is_new = (cat in ("marketplace", "repair", "car_service"))
            expected = "MEDIUM" if is_new else "LOW"
        else:
            cat, tmpl, base_amt = random.choice(LEGIT_TEMPLATES_KZ)
            lang = "kz"
            amt = base_amt + random.randint(-5000, 10000)
            text = tmpl
            is_new = (cat in ("marketplace", "repair", "car_service"))
            expected = "MEDIUM" if is_new else "LOW"

        scenarios.append({
            "id": current_id,
            "is_scam": False,
            "category": cat,
            "language": lang,
            "amount": amt,
            "is_new_recipient": is_new,
            "answer_text": text,
            "expected_risk": expected
        })
        current_id += 1
        legit_count += 1

    return scenarios


def save_dataset(scenarios: List[Dict[str, Any]], filepath: str) -> None:  # Any: Scenario items
    """Serializes dataset array into indented UTF-8 JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(scenarios, f, ensure_ascii=False, indent=2)
    print(f"Dataset saved: {filepath} (Total: {len(scenarios)} records)")


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Generate extended dataset (320 scenarios)
    dataset_320 = generate_full_dataset(320)
    save_dataset(dataset_320, os.path.join(current_dir, "scenarios_300.json"))
    
    # 2. Also ensure scenarios_100.json is available from first 100 items
    save_dataset(dataset_320[:100], os.path.join(current_dir, "scenarios_100.json"))
