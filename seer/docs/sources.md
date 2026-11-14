# Outlet websites and RSS feeds

111 of 113 TIME.mk sources resolved to a website, and 96 have an RSS feed with items from the last 7 days. In the News group, 39 of 48 have a fresh feed: enough to pick v0's 15–20 sources. Checked 2026-11-14 with [`tests/sources/resolve_sources.py`](../tests/sources/resolve_sources.py). The data is in [`sources.csv`](sources.csv).

## How a website was verified

- The script fetches candidate domains: the TIME.mk slug with `.mk`, `.com.mk` and `.com`, plus hand-picked guesses where the slug differs.
- The page title or `og:site_name` must contain the outlet's name, in Cyrillic or Latin.
- Non-`.mk` domains must contain letters only Macedonian uses (`ѓ ќ ѕ`).
- Parked, for-sale and near-empty pages are rejected.
- A feed counts as fresh if its newest item is at most 7 days old.

| Status | Count | Meaning |
| --- | --- | --- |
| Verified | 104 | The page title or site name matches the outlet |
| Checked by hand | 1 | Deutsche Welle: the page title is "Теми" and the content is in Macedonian |
| Cloudflare blocked | 6 | The domain exists but returns a bot check, so it couldn't be verified and its RSS wasn't checked |
| Not found | 2 | Фактор (faktor.mk didn't respond), Е-автомобили (no site found) |

## Findings

- **Cloudflare blocks 6 outlets**, including the daily Слободен Печат. Ingest can't read them without the outlet's cooperation or a real browser.
- **No feed found:** 24.mk, DW, Bloomberg Adria, Црнобело, Факултети, Емитер, SportSport.
- **Broken feeds:** Пари's newest item is 548 days old, and Мотори's feed is empty.
- **Renamed outlets:**
    - 24 Вести is now Телевизија 24, at [24.mk](https://wikiwand.com/en/articles/24_Vesti).
    - Весник Илинден is [vesnik-ilinden.com](https://agsm.fuen.org/en/article/fuenfzehn-jahre-seit-der-ersten-ausgabe-der-mazedonischen-zeitung-ilinden), published by Macedonians in Albania.
- **Lookalike domains that were rejected:**
    - 24vesti.com is a Serbian portal.
    - zurnal.com sells stationery.
    - dw.mk is unrelated to DW.
    - emagazin.com and agrotim.com are for sale.

## News (Вести) · 48

| Name | Website | RSS | Status |
| --- | --- | --- | --- |
| 24 Вести | [24.mk](https://24.mk) | — | verified |
| ТВ21 | [tv21.tv](https://tv21.tv) | [feed](https://tv21.tv/feed/) | verified |
| Макфакс | [makfax.com.mk](https://makfax.com.mk/) | [feed](https://makfax.com.mk/feed/) | verified |
| +инфо | [plusinfo.mk](https://plusinfo.mk) | [feed](https://plusinfo.mk/feed/) | verified |
| Сакам да кажам | [sdk.mk/index.php/mk](https://sdk.mk/index.php/mk/) | [feed](https://sdk.mk/index.php/mk/feed/) | verified |
| 360 степени | [360stepeni.mk](https://360stepeni.mk) | [feed](https://360stepeni.mk/feed/) | verified |
| Нова Македонија | [novamakedonija.com.mk](https://novamakedonija.com.mk) | [feed](https://novamakedonija.com.mk/feed/) | verified |
| Независен | [nezavisen.mk](https://nezavisen.mk) | [feed](https://nezavisen.mk/feed/) | verified |
| Deutsche Welle | [dw.com/mk](https://www.dw.com/mk) | — | checked by hand |
| Пари | [pari.mk](https://www.pari.mk/) | [feed](https://www.pari.mk/feed/) | verified, feed stale (548 days) |
| Bloomberg Adria | [mk.bloombergadria.com](https://mk.bloombergadria.com) | — | verified |
| Слободен Печат | [slobodenpecat.mk](https://slobodenpecat.mk) | — | Cloudflare blocked |
| Фокус | [fokus.mk](https://fokus.mk) | [feed](https://fokus.mk/feed/) | verified |
| Либертас | [libertas.mk](https://libertas.mk) | [feed](https://libertas.mk/feed/) | verified |
| Нова ТВ | [novatv.mk](https://novatv.mk) | [feed](https://novatv.mk/feed/) | verified |
| Бриф | [brif.mk](https://brif.mk) | — | Cloudflare blocked |
| IRL | [irl.mk/mk](https://irl.mk/mk/) | [feed](https://irl.mk/mk/feed/) | verified |
| Призма | [prizma.mk](https://prizma.mk) | [feed](https://prizma.mk/feed/) | verified |
| Мета | [meta.mk](https://meta.mk) | [feed](https://meta.mk/feed/) | verified |
| Press24 | [press24.mk](https://press24.mk) | [feed](https://press24.mk/feed/) | verified |
| Прва Скопска | [prvaskopska.mk](https://prvaskopska.mk) | [feed](https://prvaskopska.mk/feed/) | verified |
| Радио МОФ | [radiomof.mk](https://www.radiomof.mk/) | [feed](https://www.radiomof.mk/feed/) | verified |
| Пулс24 | [puls24.mk](https://puls24.mk) | [feed](https://puls24.mk/feed/) | verified |
| CivilMedia | [civilmedia.mk](https://civilmedia.mk) | [feed](https://civilmedia.mk/feed/) | verified |
| Вечер Прес | [vecer.press](https://vecer.press) | — | Cloudflare blocked |
| еМагазин | [emagazin.mk](https://emagazin.mk) | — | Cloudflare blocked |
| Frontline | [frontline.mk](https://frontline.mk) | [feed](https://frontline.mk/feed/) | verified |
| 24Инфо | [24info.mk](https://24info.mk) | [feed](https://24info.mk/feed/) | verified |
| Во Центар | [vocentar.com](https://vocentar.com) | [feed](https://vocentar.com/feed/) | verified |
| 4NEWS | [4news.mk](https://4news.mk) | [feed](https://4news.mk/feed/) | verified |
| Скопско Ехо | [skopskoeho.mk](https://skopskoeho.mk) | [feed](https://skopskoeho.mk/feed/) | verified |
| Скопје1 | [skopje1.mk](https://skopje1.mk) | [feed](https://skopje1.mk/feed/rss) | verified |
| Скопје инфо | [skopjeinfo.mk](https://skopjeinfo.mk) | [feed](https://skopjeinfo.mk/feed/) | verified |
| Рацин | [racin.mk](https://racin.mk) | [feed](https://racin.mk/feed/) | verified |
| Фактор | — | — | not found |
| Бизнис Вести | [biznisvesti.mk](https://biznisvesti.mk) | [feed](https://biznisvesti.mk/feed/) | verified |
| Порта | [porta.mk](https://porta.mk) | [feed](https://porta.mk/feed/) | verified |
| Тера | [tera.mk](https://tera.mk) | [feed](https://tera.mk/feed/) | verified |
| iNFOMAX | [infomax.mk](https://infomax.mk) | [feed](https://infomax.mk/feed/) | verified |
| Вечер | [vecer.mk](https://vecer.mk) | [feed](https://vecer.mk/feed) | verified |
| Економија и Бизнис | [ekonomijaibiznis.mk](https://ekonomijaibiznis.mk) | [feed](https://ekonomijaibiznis.mk/feed/) | verified |
| Антропол | [antropol.mk](https://antropol.mk) | [feed](https://antropol.mk/feed/) | verified |
| Политика | [politika.com.mk](https://politika.com.mk) | [feed](https://politika.com.mk/feed) | verified |
| Журнал | [zurnal.mk](https://zurnal.mk) | [feed](https://zurnal.mk/feed/) | verified |
| Проверено | [provereno.mk](https://provereno.mk) | [feed](https://provereno.mk/feed/) | verified |
| Национално | [nacionalno.mk](https://nacionalno.mk) | [feed](https://nacionalno.mk/feed/) | verified |
| Колегиум | [kolegium.mk](https://kolegium.mk) | [feed](https://kolegium.mk/feed/) | verified |
| 48часа | [48chasa.mk](https://48chasa.mk) | [feed](https://48chasa.mk/feed/) | verified |

## Portals (Портали) · 55

| Name | Website | RSS | Status |
| --- | --- | --- | --- |
| Кајгана | [kajgana.com](https://kajgana.com) | [feed](https://kajgana.com/rss.xml) | verified |
| Црнобело | [crnobelo.com](https://www.crnobelo.com/) | — | verified |
| Факултети | [fakulteti.mk](https://fakulteti.mk) | — | verified |
| IT.mk | [it.mk](https://it.mk) | — | Cloudflare blocked |
| Fashionel | [fashionel.mk](https://fashionel.mk) | [feed](https://fashionel.mk/rss) | verified |
| Таратур | [taratur.com](https://www.taratur.com/) | [feed](https://www.taratur.com/feed/) | verified |
| 365 | [365.com.mk](https://365.com.mk) | [feed](https://365.com.mk/feed/) | verified |
| Кафе пауза | [kafepauza.mk](https://kafepauza.mk) | [feed](https://kafepauza.mk/feed/) | verified |
| Попара | [popara.mk](https://popara.mk) | [feed](https://popara.mk/feed/) | verified |
| BIZlife | [bizlife.mk](https://bizlife.mk) | [feed](https://bizlife.mk/feed/) | verified |
| Убавина и Здравје | [ubavinaizdravje.mk](https://www.ubavinaizdravje.mk/) | [feed](https://www.ubavinaizdravje.mk/feed/) | verified |
| Lady | [lady.mk](https://lady.mk) | [feed](https://lady.mk/feed/) | verified |
| Порта 3 | [porta3.mk](https://www.porta3.mk/) | [feed](https://www.porta3.mk/feed/) | verified |
| Банкарство.мк | [bankarstvo.mk](https://bankarstvo.mk) | [feed](https://bankarstvo.mk/feed/) | verified |
| Деца | [deca.mk](https://deca.mk) | [feed](https://deca.mk/feed/) | verified |
| ПРВ.мк | [prv.mk](https://prv.mk) | [feed](https://prv.mk/rss) | verified |
| Д-р Митов | [drmitov.mk](https://drmitov.mk) | [feed](https://drmitov.mk/feed/) | verified |
| Екран | [ekran.mk](https://ekran.mk) | [feed](https://ekran.mk/feed/) | verified |
| Емитер | [emiter.mk](https://emiter.mk) | — | verified |
| Pedijatar.mk | [pedijatar.mk](https://pedijatar.mk) | [feed](https://pedijatar.mk/feed/) | verified |
| Градина | [gradina.mk](https://gradina.mk) | [feed](https://gradina.mk/feed/) | verified |
| Иновативност | [inovativnost.mk](https://inovativnost.mk) | [feed](https://inovativnost.mk/feed/) | verified |
| Авто Магазин | [avtomagazin.com.mk](https://www.avtomagazin.com.mk/) | [feed](https://www.avtomagazin.com.mk/feed/) | verified |
| Авто Плус | [avtoplus.mk](https://avtoplus.mk) | [feed](https://avtoplus.mk/feed/) | verified |
| Automedia | [automedia.mk](https://automedia.mk) | [feed](https://automedia.mk/feed/) | verified |
| CARClub | [carclub.mk](https://www.carclub.mk/) | [feed](https://www.carclub.mk/feed/) | verified |
| Еспресо | [espreso.mk](https://espreso.mk) | [feed](https://espreso.mk/feed/) | verified |
| Репортер | [reporter.mk](https://reporter.mk) | [feed](https://reporter.mk/feed/) | verified |
| USB | [usb.mk](https://usb.mk) | [feed](https://usb.mk/feed/) | verified |
| Агротим | [agrotim.mk](https://agrotim.mk) | — | Cloudflare blocked |
| Трн | [trn.mk](https://trn.mk) | [feed](https://trn.mk/feed/) | verified |
| Градска | [gradska.mk](https://gradska.mk) | [feed](https://gradska.mk/feed/) | verified |
| Умно | [umno.mk](https://umno.mk) | [feed](https://umno.mk/feed/) | verified |
| Битола Њуз | [bitolanews.mk](https://bitolanews.mk) | [feed](https://bitolanews.mk/feed/) | verified |
| Кумановски м. | [kumanovskimuabeti.mk](https://kumanovskimuabeti.mk) | [feed](https://kumanovskimuabeti.mk/feed/) | verified |
| Бабам Битола | [babambitola.mk](https://babambitola.mk) | [feed](https://babambitola.mk/feed/) | verified |
| Smartportal | [smartportal.mk](https://smartportal.mk) | [feed](https://smartportal.mk/feed/) | verified |
| Е-автомобили | — | — | not found |
| Зелена берза | [zelenaberza.com.mk](https://zelenaberza.com.mk) | [feed](https://zelenaberza.com.mk/feed/) | verified |
| Култура24 | [kultura24.mk](https://kultura24.mk) | [feed](https://kultura24.mk/feed/) | verified |
| Религија | [religija.mk](https://religija.mk) | [feed](https://religija.mk/feed/) | verified |
| Конект | [konekt.mk](https://konekt.mk) | [feed](https://konekt.mk/feed/) | verified |
| Булевар | [bulevar.mk](https://bulevar.mk) | [feed](https://bulevar.mk/feed/) | verified |
| Весник Илинден | [vesnik-ilinden.com](https://vesnik-ilinden.com) | [feed](https://vesnik-ilinden.com/feed/) | verified |
| Охрид1 | [ohrid1.com](https://ohrid1.com/) | [feed](https://ohrid1.com/feed) | verified |
| Шеталиште | [setaliste.mk](https://setaliste.mk) | [feed](https://setaliste.mk/feed/) | verified |
| Во Бело | [vobelo.mk](https://vobelo.mk) | [feed](https://vobelo.mk/feed/) | verified |
| Glamur | [glamur.mk](https://glamur.mk) | [feed](https://glamur.mk/feed/) | verified |
| CafeBarRestoran | [cafebarrestoran.mk](https://cafebarrestoran.mk) | [feed](https://cafebarrestoran.mk/feed/) | verified |
| Темпо | [tempo.mk](https://tempo.mk) | [feed](https://tempo.mk/feed/) | verified |
| Паноптикум | [panoptikum.mk](https://panoptikum.mk) | [feed](https://panoptikum.mk/feed/) | verified |
| Лице в лице | [licevlice.mk](https://licevlice.mk) | [feed](https://licevlice.mk/feed/) | verified |
| Автомото | [avtomoto.mk](https://avtomoto.mk) | [feed](https://avtomoto.mk/feed/) | verified |
| Sync | [sync.mk](https://sync.mk) | [feed](https://sync.mk/rss.xml) | verified |
| OhridPress | [ohridpress.com.mk](https://ohridpress.com.mk) | [feed](https://ohridpress.com.mk/feed/) | verified |

## Sports (Спортски) · 10

| Name | Website | RSS | Status |
| --- | --- | --- | --- |
| МакФудбал | [makfudbal.mk](https://makfudbal.mk) | [feed](https://makfudbal.mk/feed/) | verified |
| Спортманија | [sportmanija.mk](https://sportmanija.mk) | [feed](https://sportmanija.mk/feed/) | verified |
| IPON | [ipon.mk](https://ipon.mk) | [feed](https://ipon.mk/feed/) | verified |
| Дерби | [derbi.mk](https://derbi.mk) | [feed](https://derbi.mk/feed/) | verified |
| SportSport | [sportsport.mk](https://sportsport.mk) | — | verified |
| Sport M | [sportm.mk](https://sportm.mk) | [feed](https://sportm.mk/feed/) | verified |
| TopSport | [topsport.mk](https://topsport.mk) | [feed](https://topsport.mk/feed/) | verified |
| Спорт+ | [sportplus.mk](https://sportplus.mk) | [feed](https://sportplus.mk/feed/) | verified |
| SportStation | [sportstation.mk](https://sportstation.mk) | [feed](https://sportstation.mk/feed/) | verified |
| Мотори | [motori.mk](https://motori.mk) | [feed](https://motori.mk/?format=feed&type=rss) | verified, feed empty |

## Sources

- TIME.mk sources page: https://time.mk/s/all
- Each outlet's homepage, linked in the tables above, fetched on 2026-11-14
- 24 Вести → 24.mk: https://wikiwand.com/en/articles/24_Vesti
- Весник Илинден: https://agsm.fuen.org/en/article/fuenfzehn-jahre-seit-der-ersten-ausgabe-der-mazedonischen-zeitung-ilinden

## Assumptions

- A homepage whose title names the outlet is that outlet.
- Feed freshness was measured once, on 2026-11-14. Re-run the script before relying on it.
