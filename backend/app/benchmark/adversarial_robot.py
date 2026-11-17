"""
Adversarial Robot: Generator of sophisticated fraudulent attack scenarios.
Simulates realistic telephone fraud and social engineering vectors:
- Safe / Reserve account schemes (direct and oblique)
- Police / KNB / Prosecutors intimidation and urgency
- Family accident emergencies ('сын сбил человека', 'жол апаты')
- Smurfing evasion (amount splitting < 100k KZT to evade legacy limits)
- Social masking instructions (fraudster tells victim to lie to the bank)
- Fake broker investments and crypto withdrawals
Supports honest Train / Test dataset split per AGENTS.md.
"""

from dataclasses import dataclass, asdict
import json
import os
import random
from typing import List, Dict, Any, Tuple  # Any: Scenario data items with mixed primitives

# Seed for reproducible train/test splits
random.seed(1337)


@dataclass
class AdversarialScenario:
    """Detailed benchmark scenario model."""
    id: int
    is_scam: bool
    category: str
    language: str  # 'ru' or 'kz'
    amount: float  # in KZT
    is_new_recipient: bool
    transfer_hour: int
    frequency_last_hour: int
    answer_text: str
    attack_vector: str
    split: str  # 'train' or 'test'

    def to_dict(self) -> Dict[str, Any]:  # Any: JSON serialization mapping
        return asdict(self)


class AdversarialRobot:
    """Synthesizes high-volume adversarial scenarios with diverse evasion patterns."""

    ATTACK_VECTORS = [
        "direct_safe_account",
        "law_enforcement_threat",
        "family_accident_urgency",
        "smurfing_under_100k",
        "social_masking_deception",
        "fake_investment_broker"
    ]

    # Detailed adversarial attack templates (Russian)
    SCAM_TEMPLATES_RU = [
        # 1. Direct Safe Account
        ("direct_safe_account", "Следователь {rank} {name} приказал срочно перевести деньги на безопасный резервный счет.", 450000, 1),
        ("direct_safe_account", "Служба безопасности ЦентрКредит велела перевести сбережения на защищенный счет для сохранности.", 750000, 1),
        ("direct_safe_account", "Звонили из Национального банка, открыли мне резервную ячейку, перевод для спасения вклада.", 600000, 1),
        ("direct_safe_account", "Сотрудник финмониторинга сказал перекинуть баланс на специальный страховой счет до вечера.", 380000, 1),
        
        # 2. Law enforcement intimidation
        ("law_enforcement_threat", "Капитан полиции {name} сказал если не отправлю прямо сейчас, откроют уголовное дело за измену.", 520000, 1),
        ("law_enforcement_threat", "Звонили из КНБ, велели участвовать в секретной спецоперации и перевести средства по реквизитам.", 900000, 1),
        ("law_enforcement_threat", "Прокурор по телефону пригрозил арестом квартиры, если не оплачу спецпошлину немедленно.", 430000, 1),
        ("law_enforcement_threat", "Майор МВД требует срочный перевод для отмены подозрительной заявки на кредит на моё имя.", 680000, 1),
        
        # 3. Family accident
        ("family_accident_urgency", "Сын сбил человека на пешеходном переходе, следователь требует деньги чтобы не сажать в СИЗО!", 650000, 1),
        ("family_accident_urgency", "Внук позвонил в истерике, попал в больницу, врач требует срочно перевести на операцию чужому человеку.", 400000, 1),
        ("family_accident_urgency", "Дочь в полиции после аварии, звонит мужчина и диктует номер карты для закрытия дела.", 500000, 1),
        
        # 4. Smurfing evasion (amounts < 100k KZT to fool simple threshold rules)
        ("smurfing_under_100k", "Следователь сказал отправлять частями по 95000 тенге, чтобы финансовый контроль банка не заметил.", 95000, 3),
        ("smurfing_under_100k", "Майор велел разбить вклад на несколько переводов по 85000 тенге на разные безопасные карты.", 85000, 4),
        ("smurfing_under_100k", "Отправляю четвертый транш по 90000 тенге на резервную карту по инструкции оператора банка.", 90000, 4),
        ("smurfing_under_100k", "Сказали слать суммами до 100 тысяч чтобы не сработал лимит системы.", 98000, 3),
        
        # 5. Social masking deception (Fraudster coached victim to lie to the bank)
        ("social_masking_deception", "Звонивший майор велел сказать банку что это на покупку мебели, а сам перевожу на резервный счет.", 450000, 1),
        ("social_masking_deception", "Сказали соврать в анкете что помогаю племяннику, чтобы банк не заблокировал спасение денег.", 380000, 1),
        ("social_masking_deception", "Мне велели написать что это на ремонт квартиры, а реквизиты продиктовал сотрудник безопасности.", 550000, 1),
        
        # 6. Fake investment broker
        ("fake_investment_broker", "Брокер платформы ГазпромИнвест гарантировал доходность 150%, вношу стартовый капитал через личную карту.", 400000, 1),
        ("fake_investment_broker", "Оплата комиссии криптобиржи за вывод выигранных биткоинов по указке куратора из телеграма.", 320000, 1),
    ]

    # Detailed adversarial attack templates (Kazakh)
    SCAM_TEMPLATES_KZ = [
        # 1. Direct Safe Account (KZ)
        ("direct_safe_account", "Маған полициядан қоңырау шалды, шұғыл қауіпсіз шотқа ақша аудару керек дейді.", 500000, 1),
        ("direct_safe_account", "Банктің қауіпсіздік қызметі ақшаны сақтап қалу үшін резервтік шотқа салуды тапсырды.", 650000, 1),
        ("direct_safe_account", "Ұлттық банктің маманы арнайы сақтау шотына аударуды талап етті.", 420000, 1),
        ("direct_safe_account", "Тергеуші шұғыл қауіпсіздік шотына жіберіңіз деді, әйтпесе ақшаны ұрлап кетеді.", 720000, 1),
        
        # 2. Law enforcement intimidation (KZ)
        ("law_enforcement_threat", "ҰҚК қызметкері жедел операция өтіп жатыр деп ақшаны аударуға бұйрық берді.", 850000, 1),
        ("law_enforcement_threat", "Қаржы полициясы қылмыстық іс қозғалды деп шұғыл айыппұл төлеуді бұйырды.", 450000, 1),
        ("law_enforcement_threat", "Полиция капитаны ақшаны қазір аудармасаңыз бүкіл шотыңыз жабылады деп қорқытты.", 580000, 1),
        ("law_enforcement_threat", "Заң орындарынан хабарласып шотыңыз бұзылды тез арада басқа шотқа жіберіңіз деді.", 400000, 1),
        
        # 3. Family accident (KZ)
        ("family_accident_urgency", "Балам жол апатына түсті, тергеуші ақшаны қазір жібермесеңіз қамалады деп қорқытты.", 700000, 1),
        ("family_accident_urgency", "Немерем жылап қоңырау шалды, ауруханада жатыр, дәрігерге шұғыл ақша керек дейді.", 350000, 1),
        ("family_accident_urgency", "Қызым полицияда отыр, босату үшін мына шотқа шұғыл ақша аударыңыз деп біреулер қоңырау шалды.", 550000, 1),
        
        # 4. Smurfing evasion (KZ)
        ("smurfing_under_100k", "Қауіпсіздік қызметкері ақшаны бөліп-бөліп 90 мыңнан жібер деп нұсқау берді.", 90000, 3),
        ("smurfing_under_100k", "Тергеуші банкті алдау үшін 100 мыңнан аз қылып 85000 теңгеден аудар деді.", 85000, 3),
        ("smurfing_under_100k", "Банк тексерісінен өту үшін бөліп 95000 теңгеден резервке аударамын.", 95000, 4),
        
        # 5. Social masking deception (KZ)
        ("social_masking_deception", "Телефондағы адам банк сұраса туысыма деп айт деді, негізі шотымды сақтау үшін.", 480000, 1),
        ("social_masking_deception", "Маған жиһаз алдым деп өтірік айт деді, ал ақшаны резервтік шотқа сақтап жатырмын.", 390000, 1),
        
        # 6. Fake investment (KZ)
        ("fake_investment_broker", "Инвестициялық менеджер жеке картаға ақша аударсаңыз үлкен табыс болады деп сендірді.", 350000, 1),
        ("fake_investment_broker", "Криптовалютадан пайда түсті, оны шешіп алу үшін мына шотқа комиссия салу керек деді.", 420000, 1),
    ]

    # Legitimate non-fraud scenarios (Russian & Kazakh)
    LEGIT_TEMPLATES_RU = [
        ("gift_family", "Внуку на день рождения на подарок, обещал отправить сегодня.", 35000),
        ("gift_family", "Дочке на карманные расходы во время учебы в университете.", 20000),
        ("gift_family", "Подарок сестре на юбилей от нашей семьи.", 50000),
        ("rent_utilities", "Оплата аренды квартиры за текущий месяц хозяйке Гульнаре.", 180000),
        ("rent_utilities", "Коммунальные платежи за двухкомнатную квартиру за октябрь.", 35000),
        ("marketplace", "Покупка детской коляски на OLX, продавец отправит курьером.", 45000),
        ("marketplace", "Покупка зимней резины б/у у соседа по гаражу.", 75000),
        ("education", "Оплата курсов английского языка в языковом центре.", 60000),
        ("medical", "Оплата лечения в стоматологической клинике за пломбу.", 35000),
        ("repair", "Оплата мастеру Ерлану за замену труб и сантехники.", 40000),
        ("car_service", "Оплата СТО за замену масла и колодок.", 30000),
        ("debt_repayment", "Возврат долга коллеге по работе за билеты.", 25000),
        ("large_tuition", "Оплата семестра в университете за обучение сына (годовой контракт).", 650000),
        ("large_car_buy", "Частичный расчет за покупку подержанного автомобиля родственнику.", 850000),
    ]

    LEGIT_TEMPLATES_KZ = [
        ("gift_family", "Немереме туған күніне сыйлыққа, құттықтап жіберіп жатырмын.", 30000),
        ("gift_family", "Қызыма колледждегі күнделікті шығындары мен жолақысына.", 20000),
        ("gift_family", "Қарындасымның тойына шашу ретінде туыстар атынан.", 50000),
        ("rent_utilities", "Пәтерақы қараша айына, пәтер иесі Айнұрға аудару.", 190000),
        ("rent_utilities", "Үйдің коммуналдық қызметі мен жылу ақысына төлем.", 30000),
        ("marketplace", "OLX-тан жиһаз сатып алып жатырмын, соған төлем.", 50000),
        ("marketplace", "Көршіден көліктің қысқы дөңгелегін сатып алғанға төлем.", 65000),
        ("education", "Баланың ағылшын тілі курсына кезекті айлық төлемі.", 40000),
        ("medical", "Тіс емханасына емделгені үшін каспи арқылы төлем.", 35000),
        ("repair", "Үйдің су құбырын жөндеген шебер Қайратқа төлемақы.", 30000),
        ("car_service", "СТО-да көліктің майын ауыстырғанға төлем.", 25000),
        ("debt_repayment", "Әріптесіме түскі асқа берген қарызымды қайтарып жатырмын.", 15000),
        ("large_tuition", "Ұлымның университеттегі оқу ақысына семестрлік төлем.", 700000),
        ("large_car_buy", "Ініме көлік сатып алуға берген қаржылай көмек.", 800000),
    ]

    # --- NOVEL UNSEEN TEST TEMPLATES (Guarantees zero text overlap with train) ---
    SCAM_TEMPLATES_RU_TEST = [
        ("direct_safe_account", "Сотрудник техподдержки eGov сообщил о взломе профиля, приказал перевести на временный депозит.", 480000, 1),
        ("direct_safe_account", "Звонили из службы безопасности финансового регулятора, велели спасать сбережения на защищенной ячейке.", 710000, 1),
        ("direct_safe_account", "Инспектор по банковскому надзору требует отправить деньги на транзитный счет для проверки подлинности.", 390000, 1),
        ("law_enforcement_threat", "Следователь антикоррупционной службы {name} ведет тайную проверку и требует перевести сумму немедленно.", 540000, 1),
        ("law_enforcement_threat", "Капитан юстиции пригрозил конфискацией имущества, если не внесу судебный залог в течение часа.", 630000, 1),
        ("law_enforcement_threat", "Звонили якобы из генпрокуратуры, сказали что мои деньги спонсируют экстремистов, требуют перевода на спецсчет.", 880000, 1),
        ("family_accident_urgency", "Неизвестный представился адвокатом, сообщил что зять задержан за драку и нужны деньги на мировую.", 580000, 1),
        ("family_accident_urgency", "Сестра плачет в трубку, говорит попала в страшную аварию и просит перевести незнакомому человеку за операцию.", 670000, 1),
        ("smurfing_under_100k", "Куратор велел разбить сумму на транши по 75000 тенге, чтобы антифрод алгоритм не выдал подозрение.", 75000, 4),
        ("smurfing_under_100k", "Отправляю уже пятый перевод по 92000 тенге на дроп-карту по указке лже-сотрудника банка.", 92000, 5),
        ("smurfing_under_100k", "Сказали переводить не больше 80 тысяч тенге за раз на разные реквизиты для обхода лимитов.", 80000, 3),
        ("social_masking_deception", "Мошенник убедил меня сказать оператору что покупаю стройматериалы, а сам спасаю накопления.", 490000, 1),
        ("social_masking_deception", "По телефону проинструктировали соврать в приложении будто отправляю деньги свахе на юбилей.", 360000, 1),
        ("fake_investment_broker", "Консультант инвестиционного фонда обещала выплату дивидендов сразу после перевода на этот кошелек.", 430000, 1),
        ("fake_investment_broker", "Перевод за активацию премиального торгового робота на закрытой финансовой платформе.", 310000, 1),
    ]

    SCAM_TEMPLATES_KZ_TEST = [
        ("direct_safe_account", "eGov порталының операторы жеке кабинет бұзылды деп арнайы сақтық депозитіне аударуды тапсырды.", 490000, 1),
        ("direct_safe_account", "Қаржылық реттеу қызметінің маманы барлық ақшаны қауіпсіз ячейкаға шұғыл аударыңыз деді.", 680000, 1),
        ("law_enforcement_threat", "Сыбайлас жемқорлыққа қарсы қызметтің тергеушісі құпия операция үшін шотқа ақша салуды бұйырды.", 820000, 1),
        ("law_enforcement_threat", "Әділет департаментінен қоңырау шалып, сот шешімі шықпас үшін қазір төлем жасаңыз деп қорқытты.", 520000, 1),
        ("family_accident_urgency", "Бейтаныс заңгер хабарласып күйеу балаңыз адам қағып кетті, соттатпау үшін ақша аударыңыз деді.", 620000, 1),
        ("family_accident_urgency", "Әпкем жол апатына түсті деп бейтаныс адам шұғыл емханаға ақша сұрап жатыр.", 590000, 1),
        ("smurfing_under_100k", "Антифрод жүйесі байқамасын деп ақшаны 70000 теңгеден бөліп жіберуді тапсырды.", 70000, 4),
        ("smurfing_under_100k", "Банк тексеруінен жалтару үшін әр картаға 80 мың теңгеден аударып жатырмын.", 80000, 3),
        ("social_masking_deception", "Телефон соққан адам банк сұраса құрылысқа деп өтірік айт деді, өзім шотымды құтқарып жатырмын.", 470000, 1),
        ("fake_investment_broker", "Инвестициялық қор өкілі қосымша табыс түседі деп жеке адамның картасына ақша аудартты.", 360000, 1),
    ]

    LEGIT_TEMPLATES_RU_TEST = [
        ("wedding_service", "Оплата услуг свадебного фотографа и видеосъемки за торжество.", 85000),
        ("cottage_rental", "Аренда загородного дома на выходные дни в Боровом для семьи.", 120000),
        ("dentistry_braces", "Оплата первого взноса за установку брекет-системы в ортодонтии.", 150000),
        ("sports_fitness", "Годовой абонемент в бассейн и тренажерный зал спортивного комплекса.", 95000),
        ("garden_supplies", "Покупка саженцев плодовых деревьев и декоративных кустарников в питомнике.", 45000),
        ("appliances_repair", "Оплата мастеру за ремонт стиральной машины и замену подшипников.", 35000),
        ("pet_care", "Ветеринарные услуги и вакцинация собаки в ветклинике.", 22000),
        ("translation_legal", "Оплата услуг нотариального перевода документов и апостиля.", 28000),
        ("music_lessons", "Оплата абонемента на индивидуальные уроки игры на домбре и гитаре.", 30000),
        ("catering", "Заказ выездного кейтеринга и банкетных блюд на семейный праздник.", 75000),
    ]

    LEGIT_TEMPLATES_KZ_TEST = [
        ("wedding_service", "Үйлену тойына асаба мен фотографтың қызметіне алдын ала төлем.", 90000),
        ("cottage_rental", "Бурабайда демалыс күндеріне отбасылық коттедж жалдау ақысы.", 110000),
        ("dentistry_braces", "Стоматология клиникасында тіске брекет қойдыруға төлем.", 140000),
        ("sports_fitness", "Спорт кешеніндегі жүзу бассейніне жартыжылдық абонементке төлем.", 70000),
        ("garden_supplies", "Бау-бақшаға жеміс ағаштарының көшеттерін сатып алуға.", 40000),
        ("appliances_repair", "Үйдегі тоңазытқышты жөндеген шеберге төленген ақы.", 30000),
        ("veterinary", "Ветеринарлық клиникада мал дәрігерінің қызметіне төлеу.", 25000),
        ("traditional_event", "Құдалық дастарханына бауырсақ пен ұлттық тағамдарға тапсырыс бердім.", 45000),
        ("summer_camp", "Балаларға жазғы сауықтыру лагеріне жолдама сатып алу.", 85000),
        ("sanatorium", "Шипажайға демалуға және емделуге жолдаманың ақысын төлеу.", 160000),
    ]

    @classmethod
    def generate_benchmark_suite(
        cls,
        total_count: int = 500,
        train_ratio: float = 0.7
    ) -> List[AdversarialScenario]:
        """
        Produces 500+ balanced scenarios strictly partitioned into Train and Test.
        Train set (70%): Used to tune thresholds and regex patterns.
        Test set (30%): Unseen evaluation data for honest benchmark scoring (0 verbatim overlap with train).
        """
        scenarios: List[AdversarialScenario] = []
        train_count = int(total_count * train_ratio)
        test_count = total_count - train_count

        train_scam_count = train_count // 2
        train_legit_count = train_count - train_scam_count

        test_scam_count = test_count // 2
        test_legit_count = test_count - test_scam_count

        ranks = ["майор", "капитан", "подполковник", "следователь"]
        names = ["Иванов", "Ахметов", "Смагулов", "Ким", "Сериков"]

        current_id = 1

        # 1. Synthesize TRAIN Scams
        for i in range(train_scam_count):
            is_kz = (i % 2 == 1)
            templates = cls.SCAM_TEMPLATES_KZ if is_kz else cls.SCAM_TEMPLATES_RU
            vector, tmpl, base_amt, freq = random.choice(templates)
            amt = base_amt + random.randint(-15000, 35000)
            text = tmpl.replace("{rank}", random.choice(ranks)).replace("{name}", random.choice(names))
            hour = random.choice([1, 2, 3, 4, 23]) if (i % 5 < 2) else random.randint(9, 21)

            scenarios.append(AdversarialScenario(
                id=current_id,
                is_scam=True,
                category=vector,
                language="kz" if is_kz else "ru",
                amount=float(amt),
                is_new_recipient=True,
                transfer_hour=hour,
                frequency_last_hour=freq,
                answer_text=text,
                attack_vector=vector,
                split="train"
            ))
            current_id += 1

        # 2. Synthesize TRAIN Legit
        for i in range(train_legit_count):
            is_kz = (i % 2 == 1)
            templates = cls.LEGIT_TEMPLATES_KZ if is_kz else cls.LEGIT_TEMPLATES_RU
            cat, tmpl, base_amt = random.choice(templates)
            amt = base_amt + random.randint(-5000, 15000)
            is_new = (cat in ("marketplace", "repair", "car_service"))
            hour = random.randint(8, 22)

            scenarios.append(AdversarialScenario(
                id=current_id,
                is_scam=False,
                category=cat,
                language="kz" if is_kz else "ru",
                amount=float(amt),
                is_new_recipient=is_new,
                transfer_hour=hour,
                frequency_last_hour=1,
                answer_text=tmpl,
                attack_vector="benign_normal",
                split="train"
            ))
            current_id += 1

        # 3. Synthesize TEST Scams (strictly using novel unseen test templates)
        for i in range(test_scam_count):
            is_kz = (i % 2 == 1)
            templates = cls.SCAM_TEMPLATES_KZ_TEST if is_kz else cls.SCAM_TEMPLATES_RU_TEST
            vector, tmpl, base_amt, freq = random.choice(templates)
            amt = base_amt + random.randint(-15000, 35000)
            text = tmpl.replace("{rank}", random.choice(ranks)).replace("{name}", random.choice(names))
            hour = random.choice([1, 2, 3, 4, 23]) if (i % 5 < 2) else random.randint(9, 21)

            scenarios.append(AdversarialScenario(
                id=current_id,
                is_scam=True,
                category=vector,
                language="kz" if is_kz else "ru",
                amount=float(amt),
                is_new_recipient=True,
                transfer_hour=hour,
                frequency_last_hour=freq,
                answer_text=text,
                attack_vector=vector,
                split="test"
            ))
            current_id += 1

        # 4. Synthesize TEST Legit (strictly using novel unseen test templates)
        for i in range(test_legit_count):
            is_kz = (i % 2 == 1)
            templates = cls.LEGIT_TEMPLATES_KZ_TEST if is_kz else cls.LEGIT_TEMPLATES_RU_TEST
            cat, tmpl, base_amt = random.choice(templates)
            amt = base_amt + random.randint(-5000, 15000)
            is_new = (cat in ("cottage_rental", "appliances_repair", "catering"))
            hour = random.randint(8, 22)

            scenarios.append(AdversarialScenario(
                id=current_id,
                is_scam=False,
                category=cat,
                language="kz" if is_kz else "ru",
                amount=float(amt),
                is_new_recipient=is_new,
                transfer_hour=hour,
                frequency_last_hour=1,
                answer_text=tmpl,
                attack_vector="benign_normal",
                split="test"
            ))
            current_id += 1

        return scenarios


def generate_and_save_benchmark(
    target_path: str = "backend/app/benchmark/scenarios_500.json"
) -> Tuple[int, int]:
    """Generates and writes 500 scenarios to target JSON file."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    suite = AdversarialRobot.generate_benchmark_suite(500, train_ratio=0.7)
    
    data = [s.to_dict() for s in suite]
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    train_c = sum(1 for s in suite if s.split == "train")
    test_c = sum(1 for s in suite if s.split == "test")
    print(f"Adversarial Robot generated {len(suite)} scenarios: {train_c} Train / {test_c} Test -> {target_path}")
    return train_c, test_c


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    output_file = os.path.join(current_dir, "scenarios_500.json")
    generate_and_save_benchmark(output_file)
