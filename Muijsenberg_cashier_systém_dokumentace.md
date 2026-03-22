Masarykovo gymnázium,
SZŠ a VOŠ zdravotnická Vsetín
Thomas Muijsenberg
8.AV
Platební systém
Maturitní práce
Vedoucí práce: Mgr. Vladislav Válek
2026 

Prohlašuji, že jsem maturitní práci vypracoval/a samostatně s využitím uvedených pramenů a literatury.
Ve Vsetíně dne 17. února.
……………………………………………..
(podpis autora práce)
 

Souhlas se zveřejněním
Souhlasím se zveřejněním své maturitní práce pro potřeby školy.
Ve Vsetíně dne 17. února
……………………………………………..
(podpis autora práce)
Poděkování
Na tomto místě bych rád poděkoval Mgr. Vladislavu Válkovi za odborné vedení, pomoc a rady během zpracování této maturitní práce. Jeho podněty mi pomohly lépe uchopit zvolené téma i jednotlivé souvislosti. 
ANOTACE
Tato maturitní práce se zabývá návrhem a implementací bezhotovostního platebního systému určeného pro akce, jako jsou festivaly, školní jarmarky či trhy. Systém umožňuje účastníkům akce nabít si předplacený kredit na RFID/NFC kartu u pokladního stánku a následně bezhotovostně platit u různých prodejních stánků bez nutnosti manipulace s hotovostí. Aplikace je realizována jako webová aplikace s backendem ve frameworku Flask (Python) a databází PostgreSQL, frontend využívá vanilla JavaScript s komunikací s USB čtečkami karet prostřednictvím Web Serial API. Systém implementuje správu akcí, stánků, produktů, kategorií a zaměstnanců s rolemi (administrátor, manažer, pokladní, prodejce). Důraz je kladen na bezpečnost a integritu finančních dat – transakce jsou atomické a neměnné, aplikace využívá zamykání na úrovni řádků, idempotentní API, hashování hesel algoritmem Argon2 a parametrizované SQL dotazy. Součástí systému je také historie transakcí, statistiky prodejů, funkce undo/redo a možnost klonování akcí.
ANNOTATION
This graduation thesis deals with the design and implementation of a cashless payment system intended for events such as festivals, school fairs, or markets. The system allows event attendees to load prepaid credit onto an RFID/NFC card at a cashier booth and then pay contactlessly at various seller booths without the need to handle cash. The application is implemented as a web application with a backend built on the Flask framework (Python) and a PostgreSQL database; the frontend uses vanilla JavaScript with communication to USB card readers via the Web Serial API. The system implements management of events, booths, products, categories, and employees with roles (administrator, manager, cashier, seller). Emphasis is placed on the security and integrity of financial data – transactions are atomic and immutable, the application utilizes row-level locking, an idempotent API, Argon2 password hashing, and parameterized SQL queries. The system also includes transaction history, sales statistics, undo/redo functionality, and the ability to clone events. 

OBSAH
ÚVOD	9
1 Historie a kontext	10
1.1 Vývoj bezhotovostních platebních systémů	10
1.2 Webové technologie a jejich role	10
1.3 RFID a NFC technologie	11
2 Teoretická východiska	11
2.1 Architektura webových aplikací	11
2.2 REST API a komunikace klient-server	12
2.3 Relační databáze a transakční zpracování	12
2.4 Soft-delete vzor	13
2.5 Idempotence v síťové komunikaci	14
2.6 Zamykání a souběžný přístup	14
3 Použité technologie a nástroje	15
3.1 Python	15
3.2 Flask	15
3.3 PostgreSQL	16
3.4 JavaScript a Web Serial API	16
3.5 Další technologie a knihovny	17
4 Bezpečnostní aspekty	18
4.1 Autentizace a správa hesel	18
4.2 Správa sessions	18
4.3 Ochrana proti běžným útokům	18
4.4 Zabezpečení finančních operací	19
5 Shrnutí teoretické části a přechod k praktické části	19
PRAKTICKÁ ČÁST	21
6 Prerekvizity a instalace	21
6.1 Systémové požadavky	21
6.2 Instalace a spuštění	21
6.3 Konfigurace	22
7 Databáze a její rozvržení	22
7.1 Schéma databáze	22
7.2 Triggery a integritní omezení	24
7.3 Indexy	25
8 Způsob programování a využití nástrojů	25
8.1 Struktura projektu a Flask blueprinty	25
8.2 Připojení k databázi — psycopg a connection pool	26
8.3 Serverové sessions v PostgreSQL	27
8.4 Generátor SQL dotazů (Query Builder)	27
9 Práva přístupu	28
9.1 Hierarchie rolí	28
9.2 Vynucování oprávnění	29
9.3 Vzájemná výlučnost rolí	29
10 Čtení karet pomocí čteček	30
10.1 Komunikace přes Web Serial API	30
10.2 Ošetření chybových stavů	31
11 ACID operace a práce s databází při finančních operacích	31
11.1 Průběh platby	31
11.2 Idempotence a fingerprint	32
11.3 Refundace	33
11.4 Zajištění integrity na úrovni databáze	33
12 Caching	34
12.1 Serverový caching statických souborů	34
12.2 Klientský caching dat	34
12.3 Persistence stavu objednávky	36
13 Statistiky a historie plateb	36
13.1 Statistiky akcí	36
13.2 Historie transakcí	37
14 Kopírování (paste) a zpět/znovu (undo/redo)	38
14.1 Kopírování (paste)	38
14.2 Vrátit zpět a provést znovu (undo/redo)	39
15 Využití — jak vypadá používání aplikace	40
15.1 Přihlášení	40
15.2 Výběr akce a stánku	40
15.3 Pokladní rozhraní (index)	40
15.4 Správa akcí (event manager)	42
15.5 Správa zaměstnanců (admin)	42
15.6 Typický scénář obsluhy	43
15.6.1 Scénář pokladního (cashier):	43
15.6.2 Scénář prodejce (seller):	43
16 Bezpečnostní implementace	44
16.1 Hashování hesel	44
16.2 Rate limiting	44
16.3 Validace nahrávaných souborů	44
16.4 Ochrana cookies a sessions	44
16.5 Threat model — proti čemu se systém brání	45
16.5.1 Hrozby, proti kterým se systém aktivně brání	45
16.5.2 Co je mimo scope systému	45
17 Plánované úlohy na pozadí a logování	46
17.1 Plánované úlohy	46
17.2 Logování	46
17.2.1 Logování transakcí	47
18 Frontend a uživatelské rozhraní	47
18.1 Architektura frontendu	47
18.2 Event delegation	47
19 Testování	48
19.1 Unit testy a integrační testy	48
19.2 Kritické scénáře — platby a refundace	48
19.3 Testy undo/redo a paste	49
19.4 Další testované oblasti	49
ZÁVĚR	50
SEZNAM POUŽITÉ LITERATURY	52

 
ÚVOD
Bezhotovostní platební systémy se v posledních letech staly nedílnou součástí organizace kulturních, sportovních a společenských akcí. Tradiční hotovostní platby přinášejí řadu praktických obtíží — od nutnosti manipulovat s mincemi a bankovkami přes riziko krádeží až po zdlouhavé účtování a nemožnost sledovat prodeje v reálném čase. Moderní technologie nabízejí elegantní alternativu v podobě systémů založených na bezkontaktních kartách, které umožňují rychlé, přehledné a bezpečné transakce.
Tato práce se zabývá návrhem a realizací webové aplikace sloužící jako bezhotovostní platební systém určený primárně pro festivaly, školní akce, trhy a podobné události. Systém využívá RFID/NFC karty a čtečky k identifikaci uživatelů a jejich virtuálních peněženek. Princip fungování je jednoduchý: návštěvník akce si na pokladním stánku nabije finanční prostředky na kartu a následně může platit u libovolného prodejního stánku pouhým přiložením karty ke čtečce. Odpadá tak potřeba manipulace s hotovostí, zrychluje se obsluha a organizátoři získávají kompletní přehled o všech transakcích.
Hlavním cílem práce je vytvořit funkční, bezpečný a snadno nasaditelný platební systém, který:
●	umožní správu více souběžných akcí s různými stánky, produkty a zaměstnanci,
●	zajistí integritu finančních dat i při souběžném přístupu více uživatelů,
●	poskytne organizátorům detailní statistiky a historii transakcí,
●	bude přístupný prostřednictvím webového prohlížeče bez nutnosti instalace speciálního softwaru,
●	nabídne intuitivní a rychlé rozhraní pro obsluhu stánků.
 
1 Historie a kontext
1.1 Vývoj bezhotovostních platebních systémů
Historie bezhotovostního placení sahá až do 50. let 20. století, kdy se začaly používat první platební karty. Skutečný rozmach však přišel s rozvojem elektronických terminálů v 80. a 90. letech. Na přelomu tisíciletí se objevily první bezkontaktní technologie založené na standardech RFID (Radio-Frequency Identification) a později NFC (Near Field Communication), které umožnily platbu pouhým přiložením karty nebo telefonu k terminálu.
V prostředí festivalů a uzavřených akcí se tyto technologie začaly prosazovat přibližně od roku 2010. Systémy jako Intellipay, Tappit nebo český Albi Pay umožňují organizátorům vytvořit uzavřený platební ekosystém, ve kterém návštěvníci platí pomocí náramků nebo karet s RFID/NFC čipem. Hlavní výhody těchto systémů spočívají ve zrychlení obsluhy, eliminaci hotovosti, snadnějším účtování a možnosti sledovat prodeje v reálném čase.

1.2 Webové technologie a jejich role
Současný vývoj webových aplikací prošel za posledních dvacet let dramatickou transformací. Od statických HTML stránek se posunul k dynamickým aplikacím schopným soupeřit s desktopovým softwarem. Klíčovou roli v tomto vývoji sehrál jazyk JavaScript na straně klienta a vznik serverových frameworků v jazycích jako Python, Ruby, Java nebo JavaScript (Node.js).
Python se stal jedním z nejpopulárnějších programovacích jazyků díky své čitelnosti, rozsáhlému ekosystému knihoven a silné komunitě. V oblasti webového vývoje nabízí Python několik frameworků — od minimalistického Flasku přes robustní Django až po moderní FastAPI. Pro projekt bezhotovostního platebního systému byl zvolen Flask, jehož modulární architektura a nízká bariéra vstupu umožňují rychlý vývoj a snadnou údržbu.
Na straně databázových systémů dominuje PostgreSQL jako jeden z nejvyspělejších open-source relačních databázových systémů. PostgreSQL nabízí pokročilé funkce jako JSONB datový typ, triggery, advisory zámky a robustní transakční mechanismus, které jsou pro finanční systém klíčové.

1.3 RFID a NFC technologie
RFID (Radio-Frequency Identification) je technologie umožňující bezdrátovou identifikaci objektů pomocí rádiových vln. RFID systém se skládá ze dvou základních komponent: tagu (čipu) umístěného na identifikovaném objektu a čtečky, která vysílá rádiový signál a přijímá odpověď z tagu. Pasivní RFID tagy nemají vlastní zdroj energie — jsou napájeny elektromagnetickým polem čtečky, což umožňuje jejich miniaturizaci a nízkou cenu.
NFC (Near Field Communication) je podmnožina RFID technologie pracující na frekvenci 13,56 MHz s dosahem do přibližně 10 cm. NFC přináší oproti obecnému RFID výhodu ve standardizovaném komunikačním protokolu a široké podpoře v mobilních zařízeních. Pro platební systémy je NFC vhodná díky krátkému dosahu, který minimalizuje riziko nechtěného načtení karty, a díky rychlosti komunikace.
V kontextu tohoto projektu slouží RFID/NFC karty jako nosič jednoznačného identifikátoru (tag ID), který je při přiložení ke čtečce přenesen do webové aplikace. Čtečka je připojena k počítači přes USB a komunikuje prostřednictvím sériového portu. Webová aplikace využívá Web Serial API prohlížeče pro přímou komunikaci se čtečkou bez potřeby dalšího softwaru.

2 Teoretická východiska
2.1 Architektura webových aplikací
Webové aplikace typicky fungují na principu klient-server architektury. Klient (webový prohlížeč) odesílá HTTP požadavky na server, který je zpracuje a vrátí odpověď — nejčastěji ve formátu HTML, JSON nebo jiných datových formátů. Tato architektura přináší výhodu centralizované správy dat a logiky na serveru, zatímco klient se stará o prezentaci a uživatelskou interakci.
V moderních webových aplikacích se ustálily dva hlavní přístupy: tradiční serverové vykreslování (SSR — Server-Side Rendering), kde server generuje kompletní HTML stránky, a jednostránkové aplikace (SPA — Single Page Application), kde se počáteční stránka načte jednou a veškerá další komunikace se serverem probíhá pomocí asynchronních požadavků (AJAX/fetch), přičemž se aktualizují pouze části stránky.
Tento projekt využívá hybridní přístup — server vykresluje základní HTML šablony pomocí šablonovacího systému Jinja2, ale veškerý dynamický obsah je načítán a aktualizován prostřednictvím JavaScriptového kódu, který komunikuje s REST API endpointy serveru. Tento přístup kombinuje výhody obou metod: rychlé počáteční načtení stránky a plynulou interakci bez nutnosti znovunačítání.

2.2 REST API a komunikace klient-server
REST (Representational State Transfer) je architektonický styl pro návrh síťových aplikací. REST API definuje sadu konvencí pro komunikaci mezi klientem a serverem pomocí standardních HTTP metod:
●	GET — získání dat (čtení),
●	POST — vytvoření nového záznamu nebo provedení akce,
●	PUT/PATCH — aktualizace existujícího záznamu,
●	DELETE — smazání záznamu.
Každý endpoint API představuje určitý zdroj (resource) identifikovaný URL adresou. Server vrací data typicky ve formátu JSON, který je nativně podporován JavaScriptem a snadno zpracovatelný na obou stranách komunikace.
V tomto projektu jsou API endpointy organizovány do logických skupin (blueprintů) podle domény — transakce, uživatelé, události, produkty a další. Klient využívá nativní funkci fetch() pro komunikaci se serverem, což eliminuje závislost na externích knihovnách.

2.3 Relační databáze a transakční zpracování
Relační databáze ukládají data ve formě tabulek propojených vztahy (relacemi). Tento model, poprvé formalizovaný Edgarem F. Coddem v roce 1970, se stal standardem pro strukturovaná data díky své matematické podloženosti, flexibilitě dotazovacího jazyka SQL a silným záručním mechanismům.
Pro finanční systémy je naprosto zásadní koncept ACID transakcí:
●	Atomicita (Atomicity) — transakce je buď provedena celá, nebo vůbec. Pokud jakákoli část operace selže, všechny změny jsou vráceny zpět.
●	Konzistence (Consistency) — transakce převede databázi z jednoho platného stavu do jiného platného stavu. Všechna omezení (constraints) musí být splněna.
●	Izolace (Isolation) — souběžně probíhající transakce se navzájem neovlivňují. Každá transakce vidí konzistentní stav dat.
●	Trvanlivost (Durability) — jakmile je transakce potvrzena (committed), její změny jsou trvale uloženy i v případě výpadku systému.
V kontextu platebního systému znamená dodržení ACID vlastností například to, že platba je buď kompletně provedena (odečtena z peněženky a zaznamenána jako transakce), nebo k ní vůbec nedojde — nikdy nemůže nastat situace, kdy by se peníze odečetly, ale transakce by nebyla zaznamenána, či naopak.

2.4 Soft-delete vzor
Soft-delete je návrhový vzor, při kterém se záznamy z databáze fyzicky neodstraňují, ale pouze se označí jako smazané — typicky nastavením časového razítka do sloupce deleted_at. Tento přístup přináší několik výhod:
●	Obnovitelnost — smazané záznamy lze kdykoliv obnovit nastavením deleted_at zpět na NULL.
●	Auditní stopa — je zachována kompletní historie všech dat, což je u finančního systému obzvláště důležité.
●	Referenční integrita — záznamy, na které odkazují jiné tabulky (například transakce odkazující na smazaného uživatele), zůstávají v databázi a nedojde k porušení cizích klíčů.
●	Bezpečnost — eliminuje se riziko nechtěného nevratného smazání dat.
Nevýhodou soft-delete je nutnost přidávat podmínku WHERE deleted_at IS NULL do většiny dotazů a potenciální nárůst velikosti databáze. Tyto nevýhody jsou však v kontextu finančního systému zanedbatelné ve srovnání s přínosy.

2.5 Idempotence v síťové komunikaci
Idempotence je vlastnost operace, která zaručuje, že opakované provedení stejné operace má stejný výsledek jako její jednorázové provedení. V kontextu webových API je idempotence kriticky důležitá, protože síťová komunikace je ze své podstaty nespolehlivá — požadavek může být odeslán vícekrát kvůli výpadku spojení, opakovanému kliknutí uživatele nebo chybě na straně klienta.
U finančních transakcí má nedodržení idempotence potenciálně katastrofální důsledky — dvojité provedení platby znamená dvojité odečtení peněz z účtu. Řešením je zavedení idempotentního klíče (idempotency key), který jednoznačně identifikuje každou zamýšlenou operaci. Server si zapamatuje výsledek operace spojenéhos daným klíčem a při opakovaném požadavku se stejným klíčem vrátí uložený výsledek namísto opětovného provedení operace.

2.6 Zamykání a souběžný přístup
Souběžný přístup více uživatelů k databázi vyžaduje mechanismy, které zabrání vzájemnému narušení dat. Existuje několik úrovní zamykání:
●	Řádkové zámky (row-level locks) — zamykají konkrétní řádky v tabulce. Používají se typicky při aktualizaci konkrétního záznamu, například zůstatku peněženky.
●	Kooperativní zámky (advisory locks) — jsou zámky na úrovni aplikace, které databáze spravuje, ale nevynucuje automaticky. Aplikace je používá pro koordinaci logických operací, které by se neměly provádět souběžně.
V platebním systému se řádkové zámky využívají při manipulaci se zůstatkem peněženky — klauzule SELECT ... FOR UPDATE zajistí, že dva souběžné pokusy o platbu ze stejné peněženky nepovedou k nekonzistentnímu stavu. Kooperativní zámky slouží k zamezení souběžného provádění operací undo/redo nebo hromadného kopírování dat jedním zaměstnancem.

3 Použité technologie a nástroje
3.1 Python
Python je vysokoúrovňový, interpretovaný programovací jazyk s dynamickým typováním a automatickou správou paměti. Vyznačuje se čitelnou syntaxí, která klade důraz na srozumitelnost kódu, a rozsáhlou standardní knihovnou. Python podporuje více programovacích paradigmat — procedurální, objektově orientované i funkcionální programování.
Pro vývoj webových aplikací je Python vhodný díky široké nabídce frameworků, aktivní komunitě a velkému množství kvalitních knihoven pro práci s databázemi, zabezpečením, validací dat a dalšími úlohami. Alternativami pro vývoj webových aplikací by mohly být JavaScript/TypeScript s Node.js (výhoda sdílení jazyka mezi klientem a serverem), Java se Spring frameworkem (robustní, ale těžkopádnější), Go (vysoký výkon, ale menší ekosystém pro webový vývoj) nebo PHP s Laravelem (tradiční volba pro webové aplikace). Python s Flaskem byl zvolen pro svou jednoduchost, flexibilitu a silný ekosystém bezpečnostních knihoven.

3.2 Flask
Flask je mikroframework pro webové aplikace v Pythonu. Označení „mikro" neznamená, že by byl omezený — naopak, Flask poskytuje jádro pro zpracování HTTP požadavků, směrování, šablonování a správu sessions a umožňuje rozšíření pomocí pluginů (extensions) podle potřeb konkrétního projektu.
Hlavní výhodou Flasku oproti robustnějším frameworkům jako Django je svoboda ve výběru komponent — vývojář není nucen používat konkrétní ORM, šablonovací systém nebo autentizační mechanismus. To je obzvláště výhodné pro projekt, kde je potřeba přímá kontrola nad databázovými dotazy (namísto ORM) a vlastní implementace session mechanismu.
Flask používá systém blueprintů pro modularizaci aplikace. Blueprint je logická skupina pohledů (views), šablon a statických souborů, která může být registrována do hlavní aplikace. Tento přístup umožňuje rozdělit velkou aplikaci do samostatných, snadno spravovatelných modulů.

3.3 PostgreSQL
PostgreSQL je pokročilý open-source relační databázový systém s více než 35letou historií vývoje. Oproti jiným databázím (MySQL, SQLite, MariaDB) vyniká pokročilými funkcemi:
●	JSONB — binární formát pro ukládání JSON dat s podporou indexování a dotazování. Umožňuje kombinovat výhody relačního a dokumentového modelu.
●	Triggery — procedury automaticky spouštěné při určitých databázových událostech (INSERT, UPDATE, DELETE). Umožňují implementovat business logiku přímo na úrovni databáze.
●	Kooperativní zámky (advisory locks) — aplikační zámky spravované databází pro koordinaci souběžných operací.
●	Pokročilé indexy — parciální indexy (pouze pro podmnožinu řádků), expression indexy (nad výrazem, například LOWER(name)), GIN indexy pro JSONB.
●	Silný transakční model — plná podpora ACID s pokročilými úrovněmi izolace.
SQLite by pro tento projekt nebyl vhodný kvůli omezenému souběžnému přístupu a absenci pokročilých funkcí. MySQL by byl funkčně dostačující, ale PostgreSQL nabízí lepší podporu pro triggery, JSONB a kooperativní zámky, které jsou v projektu intenzivně využívány.

3.4 JavaScript a Web Serial API
Na straně klienta je použit čistý JavaScript (vanilla JS) bez použití frameworků jako React, Vue nebo Angular. Tento přístup eliminuje závislost na externích nástrojích pro sestavení (build tools) a zjednodušuje nasazení — stačí servírovat statické soubory bez nutnosti kompilace.
JavaScript je organizován do ES modulů (ECMAScript modules), což umožňuje logické rozdělení kódu do samostatných souborů s jasně definovanými importy a exporty. Moderní prohlížeče nativně podporují ES moduly prostřednictvím atributu type="module" ve skriptových tazích.
Web Serial API je relativně nové rozhraní prohlížeče umožňující přímou komunikaci se zařízeními připojenými přes sériový port (USB, Bluetooth). Toto API je klíčové pro čtení dat z RFID/NFC čteček bez nutnosti instalace dalšího softwaru nebo ovladačů. Web Serial API je v současnosti podporováno v prohlížečích založených na Chromiu (Google Chrome, Microsoft Edge, Opera).

3.5 Další technologie a knihovny
Projekt využívá řadu dalších technologií a knihoven:
●	psycopg 3 — moderní PostgreSQL adaptér pro Python s podporou connection poolingu, parametrizovaných dotazů a asynchronního přístupu.
●	Argon2 — vítěz soutěže Password Hashing Competition (2015), považovaný za nejbezpečnější algoritmus pro hashování hesel. Odolný vůči útokům hrubou silou i specializovanému hardwaru (GPU, ASIC).
●	Chart.js — JavaScriptová knihovna pro vytváření interaktivních grafů. Použita pro vizualizaci statistik akcí.
●	Jinja2 — šablonovací engine pro Python, integrovaný do Flasku. Umožňuje generovat HTML s dynamickým obsahem.
●	APScheduler — knihovna pro plánování periodických úloh na pozadí (například čištění expirovaných sessions).
●	Flask-Limiter — rozšíření Flasku pro omezení počtu požadavků (rate limiting) jako ochrana proti DoS útokům.
●	Pillow — knihovna pro zpracování a validaci obrázků.

4 Bezpečnostní aspekty
4.1 Autentizace a správa hesel
Autentizace je proces ověření identity uživatele. V webových aplikacích se nejčastěji provádí pomocí uživatelského jména (nebo e-mailu) a hesla. Kritickým aspektem je způsob ukládání hesel — hesla se nikdy neukládají v čitelné podobě, ale jako hash (jednosměrná transformace). Při ověření se hashuje zadané heslo a porovná se s uloženým hashem.
Moderní hashovací algoritmy pro hesla (Argon2, bcrypt, scrypt) jsou záměrně pomalé a paměťově náročné, aby ztížily útok hrubou silou. Argon2, použitý v tomto projektu, má konfigurovatelné parametry pro časovou náročnost (time cost), paměťovou náročnost (memory cost) a míru paralelismu, což umožňuje přizpůsobit bezpečnostní úroveň dostupnému hardwaru.

4.2 Správa sessions
Po úspěšné autentizaci je nutné udržovat informaci o přihlášení uživatele napříč požadavky. K tomu slouží sessions — mechanismus pro udržování stavu v jinak bezstavovém protokolu HTTP. Existují dva základní přístupy:
●	Klientské sessions — veškerá data jsou uložena v cookie na straně klienta (typicky šifrovaná a podepsaná). Výhodou je jednoduchost, nevýhodou omezená velikost a nemožnost serverové invalidace.
●	Serverové sessions — v cookie je uložen pouze identifikátor session (session ID) a vlastní data jsou uložena na serveru (v databázi, Redis, souborovém systému). Výhodou je plná kontrola nad životním cyklem session a možnost invalidace.
Pro finanční systém je serverové ukládání sessions bezpečnější, protože umožňuje okamžitou invalidaci session (například při odhlášení nebo podezření na kompromitaci) a neumožňuje klientovi manipulovat se session daty.

4.3 Ochrana proti běžným útokům
Webové aplikace čelí řadě bezpečnostních hrozeb. Mezi nejzávažnější patří:
●	SQL injection — útočník vloží škodlivý SQL kód do vstupních polí. Ochranou je důsledné používání parametrizovaných dotazů, kdy jsou uživatelská data oddělena od SQL příkazů.
●	Cross-Site Scripting (XSS) — útočník vloží škodlivý JavaScript kód, který se spustí v prohlížeči jiného uživatele. Ochranou je escapování uživatelských dat při vkládání do HTML.
●	Cross-Site Request Forgery (CSRF) — útočník přiměje přihlášeného uživatele k nevědomému provedení akce. Ochranou je nastavení cookie atributu SameSite a případně použití CSRF tokenů.
●	Brute-force útoky — systematické zkoušení hesel. Ochranou je omezení počtu pokusů o přihlášení (rate limiting).

4.4 Zabezpečení finančních operací
Finanční operace vyžadují zvláštní pozornost z hlediska bezpečnosti. Klíčové aspekty zahrnují:
●	Neměnnost záznamů — transakce jednou zapsané do systému nesmí být měnitelné ani smazatelné, aby byla zajištěna auditovatelnost a integrita finančních dat.
●	Kontrola oprávnění — každá finanční operace musí být autorizována na více úrovních (aplikační logika i databázové triggery).
●	Atomicita operací — platba musí být provedena kompletně (odečtení z peněženky + zápis transakce), nebo vůbec.
●	Ochrana proti duplicitním operacím — mechanismus idempotence zabraňuje dvojitému provedení téže platby.

5 Shrnutí teoretické části a přechod k praktické části
V teoretické části byly představeny principy a technologie, na kterých je platební systém postaven. Byly popsány koncepty webové architektury klient-server, REST API, relačních databází s ACID transakcemi, bezpečnostního zabezpečení webových aplikací a komunikace s hardwarovými zařízeními prostřednictvím Web Serial API. Dále byly představeny konkrétní technologie — Python s Flaskem, PostgreSQL, JavaScript a další knihovny — společně se zdůvodněním jejich výběru.
V následující praktické části bude podrobně popsána samotná implementace systému: struktura projektu, databázové schéma, způsob komunikace s kartovými čtečkami, systém oprávnění, finanční operace, caching, statistiky a další funkce. Praktická část obsahuje ukázky kódu, diagramy a konkrétní popisy řešení jednotlivých problémů.
 
PRAKTICKÁ ČÁST

6 Prerekvizity a instalace
6.1 Systémové požadavky
Pro spuštění aplikace je potřeba:
●	Python 3.10+ — aplikace využívá moderní syntaxi (match/case, type hints s |).
●	PostgreSQL 14+ — databázový server s podporou rozšíření pgcrypto.
●	Webový prohlížeč s podporou Web Serial API — Google Chrome, Microsoft Edge nebo Opera (pro čtení karet).
●	Git — systém správy verzí pro klonování repozitáře a správu zdrojového kódu (potřebný pouze pro instalaci)
●	RFID/NFC čtečka — připojená přes USB, komunikující přes sériový port.

6.2 Instalace a spuštění
1. Získání projektu:
git clone https://github.com/mgvsetin/2426-mp-ThomasMuij.git
cd 2426-mp-ThomasMuij
Případně stáhněte ZIP archiv projektu a rozbalte ho.
2. Vytvoření virtuálního prostředí (doporučeno):
python -m venv .venv
Aktivace (windows):
.venv\Scripts\activate
Aktivace (Linux/macOS):
source .venv/bin/activate
3. Instalace Python závislostí:
pip install -r requirements.txt
Hlavní závislosti zahrnují: Flask, psycopg (s poolem), argon2-cffi, Flask-Limiter, APScheduler, Pillow, phonenumbers, email-validator a python-dateutil.
4. Příprava databáze:
Vytvořte PostgreSQL databázi a uživatele:
CREATE DATABASE cashier_app;
Na systémech Debian/Ubuntu může být nutné doinstalovat balík postgresql-contrib pro rozšíření pgcrypto (rozšíření se aktivuje automaticky při inicializaci schématu).
Nastavte připojovací údaje buď proměnnou prostředí DATABASE_CONNINFO, nebo v souboru instance/config.py (nezapomeňte změnit heslo):
DATABASE_CONNINFO = "dbname=cashier_app host=localhost user=postgres password=heslo port=5432 options='-c timezone=UTC'"
5. Inicializace databázového schématu:
flask --app cashier_app init-db
6. Spuštění vývojového serveru:
flask --app cashier_app run
Aplikace bude dostupná na http://localhost:5000.
7. Produkční nasazení:
Pro produkci se doporučuje použít WSGI server (například Gunicorn) za reverzním proxy serverem (nginx). Nginx by měl obsluhovat statické soubory a složku s nahranými obrázky produktů. V konfiguraci je nutné:
nastavit SESSION_COOKIE_SECURE = True,
vygenerovat silný SECRET_KEY (např. python -c "import secrets; print(secrets.token_urlsafe(32))"),
nakonfigurovat PROXY_FIX podle nastavení reverzního proxy.

6.3 Konfigurace
Aplikace se konfiguruje prostřednictvím výchozích hodnot v tovární funkci create_app(), které lze přepsat souborem instance/config.py nebo proměnnými prostředí. Mezi klíčové konfigurační položky patří:
●	SECRET_KEY — tajný klíč pro podepisování sessions (v produkci nutno změnit),
●	DATABASE_CONNINFO — připojovací řetězec pro PostgreSQL,
●	READER_INFO — nastavení sériového portu pro čtečku karet (baudRate, dataBits, atd.),
●	MAX_UNDO_CHANGES — maximální počet kroků zpět (výchozí: 30),
●	REFUND_TIME_LIMIT_MINUTES — časový limit pro vrácení platby (výchozí: 5 minut),
●	MAX_CONTENT_LENGTH — maximální velikost nahrávaného souboru (výchozí: 16 MB).

7 Databáze a její rozvržení
7.1 Schéma databáze
Databáze obsahuje 17 tabulek, které lze rozdělit do několika logických skupin:
Identita a přístup:
●	employees — zaměstnanci systému (administrátoři, manažeři, pokladní, prodejci),
●	users — uživatelé/návštěvníci akcí,
●	sessions — serverové sessions pro přihlášené zaměstnance,
●	employee_event_booth_roles — přiřazení zaměstnanců k akcím a stánkům s definovanou rolí.
Struktura akcí:
●	events — akce/události,
●	booths — stánky v rámci akce (typ cashier nebo seller),
●	products — produkty s cenou a volitelným obrázkem,
●	categories — kategorie produktů,
●	product_images — metadata o obrázcích produktů.
●	product_images_failed_to_delete — záznamy o obrázcích, které se nepodařilo smazat z úložiště.
Vazební tabulky:
●	product_booth_link — přiřazení produktů ke stánkům,
●	category_booth_link — přiřazení kategorií ke stánkům,
●	category_product_link — přiřazení produktů do kategorií.
Finance:
●	wallets — virtuální peněženky vázané na kartu (tag), uživatele a akci,
●	transactions — záznam o každé finanční operaci (neměnitelný), včetně podpory pro idempotenci a refundace.
Historie změn:
●	change_history — záznam změn pro funkci undo,
●	undo_change_history — záznamy o provedených undo operacích (pro funkci redo).
 

7.2 Triggery a integritní omezení
Databáze využívá rozsáhlou soustavu triggerů, které zajišťují integritu dat přímo na úrovni databáze. Každá hlavní tabulka má BEFORE trigger, který:
●	Blokuje fyzické smazání — příkaz DELETE je zachycen a převeden na soft-delete (nastavení deleted_at = now()). Tím je zaručeno, že žádný záznam nemůže být fyzicky odstraněn z databáze.
●	Chrání neměnné sloupce — sloupce jako created_at, created_by, event_id nebo booth_type nelze po vytvoření záznamu měnit.
●	Normalizuje vstupní data — automaticky odstraňuje mezery na začátku a konci textu, převádí e-maily na malá písmena a jména na formát s velkým prvním písmenem.
Trigger na tabulce transactions je nejkomplexnější — při vkládání nové transakce provádí více než deset kontrol (aktivita akce, existence stánku, oprávnění zaměstnance, dostatečný zůstatek, shoda event_id mezi peněženkou a stánkem atd.), zamyká řádek peněženky a aktualizuje zůstatek. U refundů navíc ověřuje, že transakce odkazuje na existující platbu prostřednictvím refunded_transaction_id, že odkazovaná transakce je typu payment a že dosud nebyla refundována. Trigger také kontroluje shodu typu transakce s typem stánku — cashier stánky smí provádět pouze balance-change, zatímco seller stánky pouze payment a refund. Zároveň kompletně blokuje UPDATE i DELETE operace na této tabulce, čímž zaručuje neměnnost finančních záznamů.

7.3 Indexy
Pro zajištění výkonu dotazů jsou v databázi definovány cílené indexy:
●	Transakce — indexy na wallet_id, (event_id, occurred_at DESC) a booth_id pokrývají nejčastější dotazy pro historii a statistiky.
●	Peněženky — unikátní parciální index na (event_id, tag_id) kde deleted_at IS NULL zajišťuje, že v rámci jedné akce existuje nejvýše jedna aktivní peněženka pro danou kartu.
●	Unikátní indexy — parciální unikátní indexy (s podmínkou WHERE deleted_at IS NULL) zajišťují, že unikátní omezení platí pouze pro aktivní (nesmazané) záznamy. Například dva zaměstnanci mohou mít stejné uživatelské jméno, pokud je jeden z nich smazán.

8 Způsob programování a využití nástrojů
8.1 Struktura projektu a Flask blueprinty
Aplikace je organizována jako Flask package s modulární strukturou. Vstupním bodem je tovární funkce create_app() v souboru __init__.py, která vytváří a konfiguruje Flask instanci. Funkční logika je rozdělena do samostatných modulů, z nichž každý registruje jeden nebo více blueprintů:
cashier_app/
├── __init__.py	# Tovární funkce, konfigurace
├── auth.py	# Autentizace (login/logout) 
├── db.py	# Connection pool
├── pg_session.py	# Serverové sessions v PostgreSQL
├── transactions.py	# API: platby, dobíjení, refundace
├── users_and_wallets.py	# API: uživatelé a peněženky
├── employees.py	# API + stránka: zaměstnanci
├── events/	# Akce (CRUD, statistiky, historie)
│	├── booths.py	# Stánky
│	├── products.py	# Produkty + nahrávání obrázků
│	├── categories.py	# Kategorie
│	└── event_employees.py	# Role zaměstnanců v akcích
├── paste.py	# Kopírování/klonování
├── undo_and_redo.py	# Zpět/znovu
├── utils/	# Pomocné funkce
│	├── query_builder.py	# Generátor SQL dotazů
│	├── transactions.py	# Idempotentní vkládání transakcí
│	└── ...
├── static/	# JS, CSS, ikony
└── templates/	# Jinja2 HTML šablony
Každý modul typicky definuje dva blueprinty — jeden pro HTML stránky (s URL prefixem jako /events) a jeden pro API endpointy (s prefixem /api/events). Toto oddělení usnadňuje orientaci v kódu a umožňuje nezávislý vývoj frontend a backend částí.

8.2 Připojení k databázi — psycopg a connection pool
Pro komunikaci s PostgreSQL je použita knihovna psycopg 3 s connection poolem. Connection pool udržuje předem vytvořená připojení k databázi a přiděluje je jednotlivým požadavkům, čímž eliminuje režii opakovaného navazování spojení:
def init_app(app: Flask):
    conninfo = app.config.get('DATABASE_CONNINFO')
    pool = ConnectionPool(
        conninfo,
        kwargs={'row_factory': dict_row},
        min_size=1,
        max_size=5,
        timeout=30,
        open=True)
    app.extensions['db_pool'] = pool
Parametr row_factory=dict_row zajišťuje, že výsledky dotazů jsou vráceny jako slovníky (s názvy sloupců jako klíče), nikoli jako tuply.
Pool je uložen v app.extensions a přístupný přes funkci get_pool().
def get_pool() -> ConnectionPool:
    pool: ConnectionPool = current_app.extensions.get('db_pool')
    if pool is None:
        raise RuntimeError("db pool not initialized")
    return pool

Připojení se získává voláním get_pool().connection() jako context manager (příkaz with). Po opuštění bloku with se připojení automaticky vrátí zpět do poolu pro další požadavky — není tedy nutné ho ručně zavírat:
sql, query_params = build_insert_statement('events', params, returning='*')

    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                new_event = cur.execute(sql, query_params).fetchone()

                save_change(cur, [{
                    'table': 'events',
                    'old_values': None,
                    'new_values': convert_dict_to_serializable(dict(new_event))
                }], g.employee['id'])
    except IntegrityError as e:
        constraint = get_constraint_name(e)

        if constraint == 'unique_index_events_name_active':
            return jsonify(error='event_name_taken'), 409

        return jsonify(error='db_integrity_error'), 400

    return jsonify(), 200
Psycopg 3 používá ve výchozím nastavení transakční model — každé připojení získané z poolu automaticky zahájí transakci. Pokud blok with skončí úspěšně, transakce se potvrdí (COMMIT). Pokud dojde k výjimce, transakce se automaticky odvolá (ROLLBACK). Díky tomu je zaručena atomicita operací bez nutnosti explicitního řízení transakcí.
Veškeré SQL dotazy používají parametrizované zápisy (%s placeholdery), nikdy se nepoužívá formátování řetězců. Pro dynamické sestavování dotazů slouží modul query_builder.py, který generuje INSERT, UPDATE a DELETE příkazy s parametry.

8.3 Serverové sessions v PostgreSQL
Místo výchozího Flask mechanismu (cookie-based sessions) implementuje projekt vlastní session backend ukládající data do PostgreSQL tabulky sessions. Třída PgSessionInterface implementuje rozhraní SessionInterface a zajišťuje:
●	Generování bezpečného session ID pomocí secrets.token_urlsafe(32).
●	Ukládání session dat jako JSONB v databázi.
●	Volitelnou regeneraci session ID při přihlášení (ochrana proti session fixation).
●	Volitelné vynucování shody IP adresy a User-Agenta pro každý požadavek.
●	Automatické čištění expirovaných sessions na pozadí pomocí APScheduleru.

8.4 Generátor SQL dotazů (Query Builder)
Pro opakující se CRUD operace slouží modul query_builder.py, který na základě názvu tabulky a slovníku parametrů generuje parametrizované SQL příkazy. Tento přístup snižuje množství opakujícího se kódu a zároveň zachovává bezpečnost parametrizovaných dotazů:
sql, params = build_insert_statement(    
    'events',    
    {'name': events, 'created_by': 1},    
    returning='*'    
)
# Výsledek (jako string): INSERT INTO events (name, created_by)    
#           VALUES (%s, %s) RETURNING * 
# Doopravdy vypadá: Composed([SQL('\n    INSERT INTO '), Identifier…
# params: ['events', 1]
Query builder podporuje i pokročilé operace jako ON CONFLICT DO NOTHING (pro idempotentní vkládání) a soft-delete (generuje UPDATE ... SET deleted_at = now() místo DELETE).

9 Práva přístupu
9.1 Hierarchie rolí
Systém implementuje čtyřúrovňovou hierarchii oprávnění:
Role	Rozsah	Oprávnění
Admin	Globální	Vytváření zaměstnanců, akcí, správa smazaných záznamů, kopírování, přístup ke všem akcím a stánkům
Event manager	V rámci akce	Správa stánků, produktů, kategorií, zaměstnanců akce, zobrazení statistik a historie, přístup ke všem stánkům akce
Cashier	V rámci stánku	Správa uživatelů, vytváření/vracení peněženek, dobíjení/výběr prostředků
Seller	V rámci stánku	Provádění plateb a refundací
Role admina je uložena přímo v tabulce employees (sloupec is_admin). Ostatní role jsou definovány v tabulce employee_event_booth_roles, kde je zaměstnanec přiřazen ke konkrétní akci a případně konkrétnímu stánku. Event manager má booth_id = NULL (vztahuje se k celé akci), zatímco cashier a seller mají přiřazen konkrétní stánek.

9.2 Vynucování oprávnění
Oprávnění jsou vynucována na dvou nezávislých úrovních:
1. Aplikační vrstva — každý API endpoint na začátku ověří, zda je zaměstnanec přihlášen a zda má dostatečnou roli. Například endpoint pro vytvoření akce kontroluje logged_employee['is_admin'], endpoint pro editaci produktu ověřuje funkci is_manager().
2. Databázová vrstva — trigger na tabulce transactions nezávisle ověřuje, zda zaměstnanec provádějící transakci má odpovídající roli pro daný stánek. Toto dvojité ověření zajišťuje, že i v případě chyby v aplikační logice nemůže neoprávněný zaměstnanec provést finanční operaci.

9.3 Vzájemná výlučnost rolí
Databázový trigger na tabulce employee_event_booth_roles zajišťuje, že pokud je zaměstnanec event managerem dané akce (má přiřazení s booth_id = NULL), nemůže být zároveň přiřazen ke konkrétnímu stánku téže akce — a naopak. Toto omezení zabraňuje konfliktům v logice oprávnění.

10 Čtení karet pomocí čteček
10.1 Komunikace přes Web Serial API
Čtení RFID/NFC karet je implementováno na straně klienta pomocí Web Serial API. Celý proces probíhá v několika krocích:
1. Výběr portu — aplikace nejprve zkontroluje již spárované porty (navigator.serial.getPorts()). Pokud je spárován právě jeden port, použije se automaticky. V opačném případě je uživatel vyzván k výběru čtečky prostřednictvím systémového dialogu (navigator.serial.requestPort()).
2. Otevření portu — port se otevře s parametry definovanými v konfiguraci serveru (typicky baudRate: 9600, dataBits: 8, stopBits: 1, parity: 'none'). Tyto parametry se načítají z API endpointu /api/reader/info.
3. Čtení dat — binární proud dat ze čtečky je převeden na textový proud pomocí TextDecoderStream. Data se čtou znak po znaku a akumulují do řetězce, dokud není detekován konec ID karty znakem (\n nebo \r) nebo 100ms od posledního přečtení:
async function readStringStreamReader(reader, readableStreamClosed, onCardRead) {
  let timeoutId;

  try {
    let cardId = '';
    while (true) {
      const { value, done } = await reader.read();
      clearTimeout(timeoutId);
      if (done) {
        break;
      }

      cardId += value;

      // konec id karty, nejspíš \n nebo \r
      if (cardId.includes('\n') || cardId.includes('\r')) {
        onCardRead(cardId);
        cardId = '';
      } else {
        // nebo dost dlouho od posdledního přečtení (100ms)
        timeoutId = setTimeout(() => {
          onCardRead(cardId);
          cardId = '';
        }, 100);
      }
    }
  } catch (error) {
    console.warn('Chyba čtení:', error);
  } finally {
    clearTimeout(timeoutId);
    reader.releaseLock();
    await readableStreamClosed.catch(() => { });
  }
}
         
4. Zpracování ID — po načtení kompletního ID karty (například 00A713A700000000) je vyvolán callback, který vyhledá peněženku s odpovídajícím tag_id a zobrazí informace o uživateli.
10.2 Ošetření chybových stavů
Implementace řeší několik problematických scénářů:
●	Nepodporovaný prohlížeč — pokud prohlížeč nepodporuje Web Serial API (!('serial' in navigator)), není čtení karet možné
●	Souběžné čtení — příznak cardReaderIsBeingRead zabraňuje spuštění více čtecích smyček najednou.
●	Timeout — pokud po 100 ms od posledního přijatého znaku nepřijde další, akumulovaný řetězec je vyhodnocen jako kompletní ID (řeší situaci, kdy čtečka neposílá ukončovací znak).
●	Odpojení a opětovné připojení — událost navigator.serial.connect automaticky restartuje čtení při opětovném připojení čtečky.
●	Filtrování zařízení — konfigurace může obsahovat USB vendor/product ID filtry, které omezí výběr portů pouze na podporované čtečky.

11 ACID operace a práce s databází při finančních operacích
11.1 Průběh platby
Platba u prodejního stánku probíhá v těchto krocích:
1. Klient — zaměstnanec přiloží kartu návštěvníka ke čtečce, vybere produkty a potvrdí platbu. Klient vygeneruje unikátní idempotentní klíč (crypto.randomUUID()) a odešle požadavek na API.
2. Server — validace — server ověří přihlášení zaměstnance, existenci a aktivitu akce, oprávnění pro daný stánek, formát vstupních dat a vyhledá peněženku podle tag_id.
3. Server — vložení transakce — v rámci jedné databázové transakce se provede:
●	Výpočet SHA-256 otisku (fingerprint) ze všech parametrů požadavku.
●	Pokus o vložení záznamu do tabulky transactions s klauzulí ON CONFLICT (idempotency_key) DO NOTHING.
●	Pokud je záznam vložen, databázový trigger zamkne peněženku (FOR UPDATE), ověří dostatečný zůstatek, vypočítá balance_before/balance_after a aktualizuje zůstatek peněženky.
●	Pokud vložení selže kvůli duplicitnímu klíči, server porovná fingerprint — shoda znamená idempotentní opakování (úspěch), neshoda znamená konflikt dat (chyba 409).
4. Klient — zpracování odpovědi — při úspěchu se aktualizuje zobrazení zůstatku, při chybě se zobrazí odpovídající hlášení.

11.2 Idempotence a fingerprint
Mechanismus idempotence chrání proti duplicitním transakcím. Klient generuje unikátní klíč pro každou zamýšlenou platbu a odesílá ho v HTTP hlavičce Idempotency-Key. Server tento klíč ukládá společně s SHA-256 otiskem všech parametrů transakce:
fingerprint_source = json.dumps(
        {key: convert_uuids_to_str(value) for key, value in fingerprint_cols.items()},
        separators=(',', ':'), sort_keys=True)
    request_fingerprint = hashlib.sha256(fingerprint_source.encode('utf-8')).hexdigest()
         
Při opakovaném požadavku se stejným klíčem server rozpozná, že transakce již byla provedena. Pokud se fingerprint shoduje, jde o legitimní opakování (například kvůli výpadku sítě). Pokud se fingerprint liší, jde o pokus o zneužití klíče pro jinou transakci — server vrátí chybu.

11.3 Refundace
Refundace (vrácení platby) je speciální typ transakce, který vytvoří nový záznam s kladnou částkou a odkazem na původní transakci (refunded_transaction_id). Systém umožňuje refundovat pouze posledně provedenou platbu na dané peněžence, a to pouze v konfigurovatelném časovém limitu (výchozí: 5 minut). Podmínka pro nalezení refundovatelné transakce ověřuje, že transakce dosud nebyla refundována.

11.4 Zajištění integrity na úrovni databáze
Kromě aplikační logiky zajišťuje integritu finančních dat řada databázových mechanismů:
●	CHECK constraint balance_after = balance_before + amount_czk — matematická kontrola, že nový zůstatek odpovídá starému plus částce transakce.
●	Blokace UPDATE/DELETE na tabulce transactions — trigger vyvolá výjimku při jakémkoliv pokusu o změnu nebo smazání transakce.
●	Row-level lock (SELECT ... FOR UPDATE) — zamezuje souběžné modifikaci stejné peněženky.
●	Unikátní index na idempotency_key — zabraňuje vložení dvou transakcí se stejným klíčem.

12 Caching
12.1 Serverový caching statických souborů
Aplikace implementuje verzování statických souborů (CSS, JS) pomocí MD5 hashů. Funkce versioned_static() vypočítá hash obsahu souboru a připojí ho jako query parametr k URL:
def versioned_static(filename):
        if filename not in _static_hash_cache:
            filepath = os.path.join(app.static_folder, filename)
            try:
                with open(filepath, 'rb') as f:
                    _static_hash_cache[filename] = hashlib.md5(f.read()).hexdigest()[:10]
            except FileNotFoundError:
                _static_hash_cache[filename] = '0'
        return f'/static/{filename}?v={_static_hash_cache[filename]}'
         
Soubory s verzovacím parametrem dostávají hlavičku Cache-Control: max-age=31536000 (1 rok), protože při změně obsahu se změní hash a tím i URL — prohlížeč automaticky stáhne novou verzi. Neverzované soubory (JS moduly importované jinými moduly) dostávají Cache-Control: no-cache, aby se vždy revalidovaly.

12.2 Klientský caching dat
Na straně klienta implementuje modul cache_factory.js generickou cache pro asynchronní funkce. Tovární funkce cacheFunctionFactory obalí libovolnou async funkci a vrátí cachovanou verzi s automatickým obnovováním na pozadí:
export function cacheFunctionFactory(func, cacheTimeMs = 1000 * 60 * 2 /*2 minuty*/, cacheRefetchMs = 1000 * 60 /*1 minuta*/) {
  const cache = {
    data: null,
    fetchTime: 0
  }
  let promiseHolder;

  const wrapperFunc = (noCache = false, ...args) => {
    if (!noCache && cache.data && cache.fetchTime + cacheTimeMs > Date.now()) { // vrátí cache
      if (cache.fetchTime + cacheRefetchMs < Date.now()) {
        // refetch na pozadí (nečekej)
        wrapperFunc(true, ...args);
      }
      return Promise.resolve(cloneData(cache.data));
    }
    // aktuálně se získávají data
    if (promiseHolder) return promiseHolder;

    // získání dat vloženou funcí
    promiseHolder = (async () => {
      try {
        cache.data = await func(...args);
        cache.fetchTime = Date.now();

        return cloneData(cache.data);

      } finally {
        promiseHolder = null;
      }
    })();

    return promiseHolder;
  };

  const resetCacheFunc = () => {
    cache.data = null;
    cache.fetchTime = 0;
    wrapperFunc().catch(() => { });
  };

  return [wrapperFunc, resetCacheFunc];
}
Cache funguje ve třech režimech:
●	Cache hit (čerstvá data) — data jsou mladší než cacheRefetchMs → vrátí se okamžitě klon dat z cache.
●	Cache hit (stará data) — data jsou starší než cacheRefetchMs, ale mladší než cacheTimeMs → vrátí se klon z cache a na pozadí se spustí obnovení.
●	Cache miss — data nejsou v cache nebo jsou starší než cacheTimeMs → provede se nový fetch.
Deduplikace požadavků zabraňuje souběžnému odesílání více požadavků na stejná data — pokud je fetch již v běhu (promiseHolder), další volání čekají na výsledek prvního požadavku.
Cache se používá pro produkty, uživatele, peněženky a akce. Každý modul exportuje funkci resetCache(), která vymaže cache a spustí nový fetch na pozadí — volá se po operacích, které modifikují data (vytvoření, editace, smazání).

12.3 Persistence stavu objednávky
Třída Order na straně klienta ukládá aktuální stav objednávky (košíku) do sessionStorage prohlížeče. Díky tomu objednávka přežije obnovení stránky (refresh) v rámci stejné záložky, ale automaticky se vymaže po zavření záložky.

13 Statistiky a historie plateb
13.1 Statistiky akcí
Endpoint /api/events/<event_id>/statistics vrací komplexní statistický přehled akce. Data jsou rozdělena do několika kategorií:
●	Celkové statistiky — počet transakcí, unikátních peněženek a uživatelů, celkové tržby, celkové vklady a výběry.
●	Statistiky stánků — rozložení tržeb, transakcí, vkladů a výběrů po jednotlivých stáncích.
●	Statistiky produktů — prodané množství, celkové tržby a průměrná cena pro každý produkt. Data se extrahují z JSONB sloupce products_info v tabulce transactions pomocí funkce jsonb_array_elements.
●	Top 10 produktů — žebříček nejprodávanějších produktů podle tržeb.
●	Hodinové a denní statistiky — časový průběh transakcí, tržeb a vkladů agregovaný pomocí DATE_TRUNC.
●	Statistiky peněženek — počet peněženek, celkový, průměrný, maximální a minimální zůstatek.
●	Statistiky stánků × produktů — detailní rozpad prodejů produktů po stáncích.
Všechny statistické dotazy vylučují refundované transakce pomocí podmínky NOT EXISTS (SELECT 1 FROM transactions r WHERE r.refunded_transaction_id = t.id), čímž zajišťují, že refundované platby nezkreslují statistiky.
 

13.2 Historie transakcí
Aplikace poskytuje dva typy historie transakcí:
●	Historie transakcí uživatele — zobrazuje všechny transakce konkrétního uživatele v rámci akce, včetně názvu stánku, jména zaměstnance, částek, zůstatků a informací o produktech. Přístupná z pohledu pokladního (cashier) i manažera akce.
●	Historie transakcí akce — zobrazuje kompletní výpis všech transakcí celé akce. Přístupná pouze pro event managery a adminy.
Obě historie jsou zobrazeny na dedikovaných HTML stránkách s tabulkovým zobrazením.
 
14 Kopírování (paste) a zpět/znovu (undo/redo)
14.1 Kopírování (paste)
Endpoint POST /api/paste umožňuje klonování entit v rámci systému. Jedná se o operaci dostupnou pouze administrátorům (pro vytváření nových zaměstnanců a akcí) a event manažerům (pro klonování v rámci akce). Podporované operace:
●	Klonování zaměstnanců — zkopíruje zaměstnance včetně přiřazení rolí. Generuje unikátní uživatelské jméno a e-mail přidáním suffixu _copy, _copy2 atd.
●	Klonování akcí — vytvoří novou akci se všemi stánky, produkty, kategoriemi a vazebnými tabulkami.
●	Klonování stánků — zkopíruje obsah stánku (produkty, kategorie, přiřazení zaměstnanců) do cílových stánků nebo nových akcí.
●	Klonování produktů a kategorií — jednotlivé nebo hromadné kopírování.
Všechny vazební tabulky se vkládají s klauzulí ON CONFLICT DO NOTHING, aby nedošlo k chybě při duplicitních vazbách. Celá operace probíhá v rámci jedné databázové transakce a je chráněna advisory lockem (pg_try_advisory_xact_lock) proti souběžnému provádění.
Každá operace paste ukládá změny do change_history, takže ji lze vrátit zpět pomocí undo.

14.2 Vrátit zpět a provést znovu (undo/redo)
Systém implementuje generický mechanismus undo/redo pro všechny CRUD operace nad správou akcí, stánků, produktů, kategorií a zaměstnanců. Finanční transakce undo nepodléhají — pro vrácení platby slouží refundace.
Princip fungování:
Každá operace, která mění data (vytvoření, editace, smazání), volá funkci save_change(), která zapíše do tabulky change_history JSON popis změny:
save_change(cur, [{
        'table': 'products',
        'old_values': {'id': '...', 'name': 'Hamburger',
                       'price': 50},
        'new_values': {'id': '...', 'name': 'Cheeseburger',
                       'price': 65}
    }], employee_id)
Konvence: old_values=None znamená INSERT (nový záznam), new_values=None znamená DELETE, obojí nastavené znamená UPDATE.
Undo — nalezne nejnovější nezrušenou změnu daného zaměstnance a aplikuje ji v opačném směru (INSERT → smazání, DELETE → obnovení, UPDATE → obnova starých hodnot). Změny se aplikují ve správném pořadí — nejprve obnovení smazaných rodičů, poté aktualizace, nakonec smazání vložených dětí.
Redo — nalezne nejnověji zrušenou změnu (záznam v undo_change_history) a znovu ji aplikuje. Pořadí je opačné oproti undo.
Bezpečnostní opatření:
●	Advisory lock zabraňuje souběžnému undo/redo stejným zaměstnancem.
●	Konfigurovatelný časový limit (výchozí: 60 minut) a maximální počet kroků (výchozí: 30).
●	Detekce konfliktů — pokud byla entita mezitím smazána jiným uživatelem, operace vrátí informaci o konfliktu místo chyby.
●	Po každé operaci se provedou vazební kontroly — před obnovením vazebního záznamu se ověří, že odkazované entity stále existují.

15 Využití — jak vypadá používání aplikace
15.1 Přihlášení
Zaměstnanec se přihlásí uživatelským jménem nebo e-mailem a heslem na přihlašovací stránce. Po úspěšném přihlášení je přesměrován na hlavní stránku.

15.2 Výběr akce a stánku
Po přihlášení si zaměstnanec vybere akci, ke které má přiřazenou roli. Podle typu role se mu zobrazí odpovídající rozhraní:
●	Admin — vidí všechny akce, může přejít do správy akcí, zaměstnanců nebo nastavení.
●	Event manager — vidí akce, kde je manažerem, a může je spravovat.
●	Cashier/Seller — po výběru akce si vybere stánek a přejde do pokladního rozhraní.

15.3 Pokladní rozhraní (index)
Hlavní pracovní stránka slouží pro obsluhu zákazníků:
●	Načtení karty — přiložením karty ke čtečce se automaticky identifikuje peněženka a zobrazí se jméno uživatele a aktuální zůstatek.
●	Cashier stánek — zaměstnanec může vytvářet uživatele, vytvářet a vracet peněženky, dobíjet a vybírat prostředky. Zobrazuje se seznam uživatelů s možností vyhledávání.
 
●	Seller stánek — zaměstnanec vidí seznam produktů (s obrázky a cenami), vybírá produkty do košíku, potvrzuje platbu. Může také provést refundaci poslední platby.
 

15.4 Správa akcí (event manager)
Rozhraní pro správce akce umožňuje:
●	Vytvářet, editovat a mazat stánky (cashier/seller).
●	Spravovat produkty — přidávat, editovat, mazat, nahrávat obrázky, přiřazovat ke stánkům a kategoriím.
●	Spravovat kategorie produktů a jejich přiřazení ke stánkům.
●	Přiřazovat zaměstnance k rolím v rámci akce.
●	Zobrazovat statistiky a historii transakcí.
 

15.5 Správa zaměstnanců (admin)
Administrátor může vytvářet nové zaměstnance, editovat jejich údaje (uživatelské jméno, heslo), mazat je a zobrazovat smazané zaměstnance s možností obnovení.
 
15.6 Typický scénář obsluhy
Pro lepší představu o každodenním používání systému zde popisuji dva typické scénáře:
15.6.1 Scénář pokladního (cashier):
Pokladní se ráno přihlásí do systému, vybere dnešní akci (například „Školní jarmark 2026") a svůj pokladní stánek. Přijde první návštěvník, který si chce nabít kartu. Pokladní zadá jméno, příjmení a volitelně email, heslo nebo jiný identifikátor návštěvníka. Pokud už existuje, tak ho pouze vybere, jinak vytvoří nového uživatele. Vytvoří mu peněženku přiložením návštěvníkovy RFID karty ke čtečce — systém automaticky načte tag ID karty a přiřadí ho k peněžence. Poté pokladní zadá částku (například 500 Kč), potvrdí dobití a návštěvník může odejít a platit u prodejních stánků. Když se návštěvník vrátí a chce dobít další prostředky, stačí přiložit kartu — systém ho ihned identifikuje a pokladní pouze zadá novou částku. Na konci akce může návštěvník přijít pro výběr zbývajících prostředků a vrácení karty.
15.6.2 Scénář prodejce (seller):
Prodejce si po přihlášení vybere svůj prodejní stánek. Na obrazovce vidí vlevo seznam produktů rozdělený do kategorií (například „Jídlo", „Nápoje"), vpravo košík s aktuální objednávkou. Když přijde zákazník a objedná si hamburger a limonádu, prodejce klikne na příslušné produkty — ty se přidají do košíku s celkovou cenou. Zákazník přiloží kartu ke čtečce a prodejce potvrdí platbu jedním kliknutím. Systém okamžitě odečte částku z peněženky a potvrdí platbu. Pokud zákazník zjistí, že dostal špatnou objednávku, nebo prodejce udělá jakoukoli chybu, prodejce může do 5 minut provést refundaci poslední platby. Celý proces jedné transakce tak trvá jen několik sekund.
16 Bezpečnostní implementace
16.1 Hashování hesel
Hesla jsou hashována algoritmem Argon2id s parametry time_cost=3, memory_cost=65536 (64 MB), parallelism=2. Při každém přihlášení se kontroluje, zda parametry hashe odpovídají aktuální konfiguraci — pokud ne, provede se automatický rehash. Tento mechanismus umožňuje transparentní zvýšení bezpečnostních parametrů v budoucnu bez nutnosti resetovat hesla.

16.2 Rate limiting
Omezení počtu požadavků chrání proti brute-force útokům a nadměrnému zatížení serveru. Globální limit je 300 požadavků za minutu. Endpoint pro přihlášení má přísnější limit 10 pokusů za 15 minut.

16.3 Validace nahrávaných souborů
Nahrávání obrázků produktů podléhá několika vrstvám validace:
●	Maximální velikost souboru: 16 MB (MAX_CONTENT_LENGTH).
●	Povolené MIME typy: image/jpeg, image/png, image/webp.
●	Povolené přípony: .jpeg, .jpg, .png, .webp.
●	Maximální rozlišení: 50 milionů pixelů (kontrola pomocí knihovny Pillow).
●	Obrázky jsou uloženy mimo adresář aplikace v konfigurovaném UPLOAD_FOLDER.

16.4 Ochrana cookies a sessions
Session cookie je zabezpečena nastavením:
●	HttpOnly = True — cookie není přístupná z JavaScriptu, čímž se eliminuje riziko krádeže session ID prostřednictvím XSS útoku.
●	SameSite = Lax — cookie se neodesílá při cross-site požadavcích (ochrana proti CSRF).
●	Secure = True (v produkci) — cookie se odesílá pouze přes HTTPS.

16.5 Threat model — proti čemu se systém brání
Systém je navržen s ohledem na hrozby typické pro platební systémy provozované na akcích s fyzickým přístupem obsluhy k zařízením:
16.5.1 Hrozby, proti kterým se systém aktivně brání
●	Neoprávněný přístup k systému — řešeno autentizací (Argon2 hesla), hierarchií rolí a rate limitingem přihlašování.
●	Manipulace s finančními záznamy — transakce jsou na úrovni databáze neměnné (triggery blokují UPDATE/DELETE). Soft-delete vzor zajišťuje, že žádná data nejsou fyzicky smazána. Finanční záznamy nemůže měnit ani admin.
●	Duplicitní provedení platby — mechanismus idempotence s SHA-256 fingerprintem zabraňuje dvojitému stržení prostředků.
●	SQL injection a XSS — parametrizované dotazy na backendu a escapování uživatelských dat na frontendu (funkce escapeHTML()).
●	Neoprávněná finanční operace — dvojí ověření oprávnění (aplikační vrstva + databázový trigger) zajišťuje, že ani chyba v aplikační logice neumožní neoprávněnou transakci.
●	Brute-force útoky na přihlášení — rate limiting (10 pokusů za 15 minut).
●	Krádež session — HttpOnly a SameSite cookies, volitelné vynucování IP adresy a User-Agenta.
16.5.2 Co je mimo scope systému
●	Fyzická bezpečnost čteček a zařízení — systém neposkytuje ochranu proti fyzické manipulaci s hardwarem (například výměna čtečky za podvržené zařízení). Předpokládá se, že organizátor akce zajišťuje fyzickou bezpečnost stánků.
●	Šifrování komunikace karta–čtečka — RFID/NFC tag ID je přenášeno v otevřené podobě. Systém se spoléhá na krátký dosah NFC a na to, že tag ID samotné bez přístupu do systému nemá hodnotu.
●	DDoS útoky na infrastrukturu — základní rate limiting chrání proti jednoduchým útokům, ale ochrana proti distribuovaným útokům závisí na infrastruktuře (firewall, reverzní proxy).

17 Plánované úlohy na pozadí a logování
17.1 Plánované úlohy
Aplikace využívá APScheduler pro periodické úlohy na pozadí:
●	Čištění sessions — každých 60 minut se smažou sessions, které jsou neaktivní déle než nakonfigurovaný limit (výchozí: 7 dní).
●	Čištění nepoužívaných obrázků — každé 3 hodiny se identifikují obrázky, na které neodkazuje žádný produkt, a odstraní se z databáze i disku.
●	Čištění sirotčích obrázků na disku — každých 12 hodin se zkontroluje, zda na disku nejsou soubory, které nemají odpovídající záznam v databázi.
Pro prostředí s více WSGI workery (například Gunicorn) zajišťuje filelock, že scheduler běží pouze v jednom z workerů, čímž se zabraňuje duplicitnímu provádění úloh.
17.2 Logování
Pro finanční systém je logování důležitou součástí provozu — umožňuje zpětně dohledat příčinu problémů, sledovat neočekávané chování a ověřovat správný běh systému. Aplikace využívá standardní Python logging modul integrovaný do Flasku (current_app.logger):
●	Chyby (exception) — neočekávané výjimky při operacích se zaměstnanci, peněženkami, událostmi, produkty a dalšími entitami jsou logovány s kompletním tracebackem pomocí current_app.logger.exception().
●	Varování (warning) — konflikty při undo/redo operacích (například pokus o obnovení entity smazané jiným uživatelem) jsou logovány jako varování, aby bylo možné zpětně zjistit, proč operace neskončila standardním způsobem.
●	Informační záznamy (info) — plánované úlohy na pozadí logují svůj průběh: počet vyčištěných sessions, dokončení čištění obrázků a další provozní informace.
●	Chyby scheduleru — všechny plánované úlohy jsou obaleny try-except bloky a případné výjimky jsou zaznamenány pomocí logger.error(), aby selhání jedné úlohy nenarušilo běh ostatních.
V produkčním nasazení lze logování nakonfigurovat na výstup do souboru nebo externího systému. 
17.2.1 Logování transakcí
Samotné finanční transakce nejsou logovány do log souboru — jejich kompletní a neměnná historie je uložena přímo v databázi (tabulka transactions), což slouží jako primární auditní záznam.
18 Frontend a uživatelské rozhraní
18.1 Architektura frontendu
Frontend je postaven na čistém JavaScriptu bez použití frameworků (React, Vue, Angular). Kód je organizován do ES modulů, kde každý modul odpovídá za jednu funkční oblast (produkty, uživatelé, peněženky, objednávky, karty atd.). HTML šablony jsou generovány na serveru pomocí Jinja2 a poskytují základní strukturu stránky, zatímco veškerý dynamický obsah je načítán a aktualizován pomocí JavaScriptu.
Komunikace se serverem probíhá výhradně přes fetch() API. Dynamický HTML obsah se vytváří pomocí template literálů a vkládá do DOM. Všechna uživatelská data jsou před vložením do HTML escapována funkcí escapeHTML() pro ochranu proti XSS útokům.

18.2 Event delegation
Pro efektivní zpracování událostí na dynamicky generovaném obsahu se používá vzor event delegation — posluchače událostí jsou registrovány na elementu document a pomocí kontroly event.target se identifikuje konkrétní element, na kterém událost nastala. Tento přístup eliminuje nutnost přiřazovat posluchače jednotlivým elementům po každém překreslení obsahu.

19 Testování
Projekt obsahuje rozsáhlou sadu automatizovaných testů implementovaných pomocí frameworku pytest. Testy pokrývají jak izolovanou logiku jednotlivých komponent, tak integrační scénáře zahrnující skutečnou databázi.

19.1 Unit testy a integrační testy
Testy v projektu lze rozdělit do dvou kategorií:
●	Unit testy — testují izolovanou logiku bez závislosti na databázi. Například testy v test_undo_redo.py ověřují správné řazení změn pro operace undo a redo (rodičovské záznamy se obnovují před dětskými, aby nedošlo k porušení referenční integrity), detekci typu změny (insert/update/delete) a filtrování neúčinných změn.
●	Integrační testy — většina testů v projektu pracuje s reálnou PostgreSQL databází. Sdílený fixture db_pool v souboru conftest.py vytváří connection pool k testovací databázi, inicializuje schéma a po každém testu provede rollback, aby byl zajištěn čistý stav. Testy tak ověřují celý řetězec od HTTP požadavku přes aplikační logiku, SQL dotazy a databázové triggery až po odpověď.

19.2 Kritické scénáře — platby a refundace
Testy finančních operací patří k nejdůležitějším, protože chyba v platební logice má přímý finanční dopad:
●	Průběh platby — testy ověřují kompletní průběh platby včetně správného výpočtu balance_before/balance_after, odečtení z peněženky a vytvoření záznamu transakce. Testují se jak úspěšné platby, tak odmítnutí při nedostatečném zůstatku (InsufficientBalanceError).
●	Idempotence — testy ověřují, že opakovaný požadavek se stejným idempotentním klíčem nevytvoří duplicitní transakci, a že požadavek se stejným klíčem, ale jinými parametry, vrátí chybu 409 (IdempotencyKeyDataConflict).
●	Refundace — testuje se, že refundace vytvoří novou transakci s kladnou částkou, správně odkáže na původní transakci a že nelze refundovat již refundovanou transakci.
●	Souběžné transakce — testy simulují souběžný přístup ke stejné peněžence z více vláken a ověřují, že řádkové zámky (FOR UPDATE) zajistí konzistentní stav i při paralelním zpracování.

19.3 Testy undo/redo a paste
●	Undo/redo — testy ověřují správné pořadí aplikace změn (při undo se smazané záznamy obnovují před dětskými, při redo se vkládají v originálním pořadí), detekci typu operace a filtrování změn, které by neměly žádný efekt.
●	Paste/klonování — testy pokrývají klonování akcí, zaměstnanců a jejich přiřazení, generování unikátních názvů (sufix _copy, _copy2 atd.) a ověření autorizace (pouze admin může klonovat zaměstnance a akce).

19.4 Další testované oblasti
●	Autentizace — přihlášení, odhlášení, ověřování hesel s rehashováním, rate limiting.
●	CRUD operace — vytváření, editace, mazání a obnovování záznamů, validace vstupů, kontrola oprávnění.
●	Databázové trigger — testy ověřují, že triggery správně blokují fyzické smazání, chrání neměnné sloupce a normalizují data.
●	Validace vstupů — testy pokrývají chybné formáty (neplatné UUID, záporné ceny, příliš dlouhé řetězce) a ověřují, že server vrací odpovídající HTTP kódy (400, 401, 403, 409).
Testy se spouštějí příkazem pytest a pro jejich běh je vyžadována běžící instance PostgreSQL s testovací databází.

ZÁVĚR
Cílem této práce bylo navrhnout a implementovat bezhotovostní platební systém pro akce, který by byl bezpečný, spolehlivý a snadno použitelný. Na základě provedené implementace a popisu v předchozích kapitolách lze zhodnotit naplnění stanovených cílů:
Správa více souběžných akcí — systém plně podporuje více akcí probíhajících současně, každá s vlastní sadou stánků, produktů, kategorií a zaměstnanců. Hierarchie rolí zajišťuje, že každý zaměstnanec vidí a může spravovat pouze akce a stánky, ke kterým má oprávnění.
Integrita finančních dat — kombinace ACID transakcí PostgreSQL, databázových triggerů blokujících modifikaci transakcí, řádkových zámků na peněženkách a mechanismu idempotence zajišťuje, že finanční data jsou v každém okamžiku konzistentní. Dvojí vrstva ověřování oprávnění (aplikační + databázová) minimalizuje riziko neoprávněných operací.
Statistiky a historie — organizátoři mají k dispozici detailní statistiky na úrovni celé akce, jednotlivých stánků i produktů, včetně časových průběhů a žebříčků. Kompletní historie transakcí je přístupná jak pro jednotlivé uživatele, tak pro celou akci.
Přístupnost přes webový prohlížeč — aplikace nevyžaduje instalaci žádného speciálního softwaru. Pro čtení karet stačí prohlížeč podporující Web Serial API (Chrome, Edge). Frontend funguje plně v prohlížeči, bez nutnosti build procesu nebo externích závislostí.
Intuitivní rozhraní — pokladní rozhraní je navrženo pro rychlou obsluhu: přiložení karty automaticky identifikuje zákazníka, výběr produktů a potvrzení platby probíhá několika kliknutími. Systém undo/redo a kopírování usnadňuje správu akcí.
 
Projekt ukazuje, že i s relativně jednoduchými technologiemi (Python, Flask, PostgreSQL, vanilla JavaScript) je možné vytvořit robustní finanční systém s pokročilými funkcemi. Klíčovým rozhodnutím bylo přesunout významnou část business logiky do databázových triggerů, čímž se zajistila integrita dat nezávisle na aplikační vrstvě. Tento přístup sice zvyšuje složitost databázového schématu, ale výrazně snižuje riziko nekonzistentních dat.
Mezi možná budoucí rozšíření patří podpora mobilních zařízení s NFC pro čtení karet, implementace exportu statistik do formátů CSV/PDF, rozšíření systému o online dobíjení prostřednictvím platební brány nebo přidání vícejazyčné podpory rozhraní.
 
SEZNAM POUŽITÉ LITERATURY
