/**
 * @file Vstup telefonního čísla s výběrem mezinárodní předvolby.
 */
const countryCodes = [
  { code: '', country: 'Žádné', nativeName: 'Žádné předčíslí', flag: '' },
  { code: '+1', country: 'USA / Kanada', nativeName: 'USA / Canada', flag: '🇺🇸' },
  { code: '+7', country: 'Rusko', nativeName: 'Россия', flag: '🇷🇺' },
  { code: '+20', country: 'Egypt', nativeName: 'مصر', flag: '🇪🇬' },
  { code: '+27', country: 'Jihoafrická republika', nativeName: 'South Africa', flag: '🇿🇦' },
  { code: '+30', country: 'Řecko', nativeName: 'Ελλάδα', flag: '🇬🇷' },
  { code: '+31', country: 'Nizozemsko', nativeName: 'Nederland', flag: '🇳🇱' },
  { code: '+32', country: 'Belgie', nativeName: 'België / Belgique', flag: '🇧🇪' },
  { code: '+33', country: 'Francie', nativeName: 'France', flag: '🇫🇷' },
  { code: '+34', country: 'Španělsko', nativeName: 'España', flag: '🇪🇸' },
  { code: '+36', country: 'Maďarsko', nativeName: 'Magyarország', flag: '🇭🇺' },
  { code: '+39', country: 'Itálie', nativeName: 'Italia', flag: '🇮🇹' },
  { code: '+40', country: 'Rumunsko', nativeName: 'România', flag: '🇷🇴' },
  { code: '+41', country: 'Švýcarsko', nativeName: 'Schweiz / Suisse', flag: '🇨🇭' },
  { code: '+43', country: 'Rakousko', nativeName: 'Österreich', flag: '🇦🇹' },
  { code: '+44', country: 'Spojené království', nativeName: 'United Kingdom', flag: '🇬🇧' },
  { code: '+45', country: 'Dánsko', nativeName: 'Danmark', flag: '🇩🇰' },
  { code: '+46', country: 'Švédsko', nativeName: 'Sverige', flag: '🇸🇪' },
  { code: '+47', country: 'Norsko', nativeName: 'Norge', flag: '🇳🇴' },
  { code: '+48', country: 'Polsko', nativeName: 'Polska', flag: '🇵🇱' },
  { code: '+49', country: 'Německo', nativeName: 'Deutschland', flag: '🇩🇪' },
  { code: '+51', country: 'Peru', nativeName: 'Perú', flag: '🇵🇪' },
  { code: '+52', country: 'Mexiko', nativeName: 'México', flag: '🇲🇽' },
  { code: '+53', country: 'Kuba', nativeName: 'Cuba', flag: '🇨🇺' },
  { code: '+54', country: 'Argentina', nativeName: 'Argentina', flag: '🇦🇷' },
  { code: '+55', country: 'Brazílie', nativeName: 'Brasil', flag: '🇧🇷' },
  { code: '+56', country: 'Chile', nativeName: 'Chile', flag: '🇨🇱' },
  { code: '+57', country: 'Kolumbie', nativeName: 'Colombia', flag: '🇨🇴' },
  { code: '+58', country: 'Venezuela', nativeName: 'Venezuela', flag: '🇻🇪' },
  { code: '+60', country: 'Malajsie', nativeName: 'Malaysia', flag: '🇲🇾' },
  { code: '+61', country: 'Austrálie', nativeName: 'Australia', flag: '🇦🇺' },
  { code: '+62', country: 'Indonésie', nativeName: 'Indonesia', flag: '🇮🇩' },
  { code: '+63', country: 'Filipíny', nativeName: 'Pilipinas', flag: '🇵🇭' },
  { code: '+64', country: 'Nový Zéland', nativeName: 'New Zealand', flag: '🇳🇿' },
  { code: '+65', country: 'Singapur', nativeName: 'Singapore', flag: '🇸🇬' },
  { code: '+66', country: 'Thajsko', nativeName: 'ประเทศไทย', flag: '🇹🇭' },
  { code: '+81', country: 'Japonsko', nativeName: '日本', flag: '🇯🇵' },
  { code: '+82', country: 'Jižní Korea', nativeName: '대한민국', flag: '🇰🇷' },
  { code: '+84', country: 'Vietnam', nativeName: 'Việt Nam', flag: '🇻🇳' },
  { code: '+86', country: 'Čína', nativeName: '中国', flag: '🇨🇳' },
  { code: '+90', country: 'Turecko', nativeName: 'Türkiye', flag: '🇹🇷' },
  { code: '+91', country: 'Indie', nativeName: 'भारत', flag: '🇮🇳' },
  { code: '+92', country: 'Pákistán', nativeName: 'پاکستان', flag: '🇵🇰' },
  { code: '+93', country: 'Afghánistán', nativeName: 'افغانستان', flag: '🇦🇫' },
  { code: '+94', country: 'Srí Lanka', nativeName: 'ශ්‍රී ලංකා', flag: '🇱🇰' },
  { code: '+95', country: 'Myanmar', nativeName: 'မြန်မာ', flag: '🇲🇲' },
  { code: '+98', country: 'Írán', nativeName: 'ایران', flag: '🇮🇷' },
  { code: '+211', country: 'Jižní Súdán', nativeName: 'South Sudan', flag: '🇸🇸' },
  { code: '+212', country: 'Maroko', nativeName: 'المغرب', flag: '🇲🇦' },
  { code: '+213', country: 'Alžírsko', nativeName: 'الجزائر', flag: '🇩🇿' },
  { code: '+216', country: 'Tunisko', nativeName: 'تونس', flag: '🇹🇳' },
  { code: '+218', country: 'Libye', nativeName: 'ليبيا', flag: '🇱🇾' },
  { code: '+220', country: 'Gambie', nativeName: 'Gambia', flag: '🇬🇲' },
  { code: '+221', country: 'Senegal', nativeName: 'Sénégal', flag: '🇸🇳' },
  { code: '+222', country: 'Mauritánie', nativeName: 'موريتانيا', flag: '🇲🇷' },
  { code: '+223', country: 'Mali', nativeName: 'Mali', flag: '🇲🇱' },
  { code: '+224', country: 'Guinea', nativeName: 'Guinée', flag: '🇬🇳' },
  { code: '+225', country: 'Pobřeží slonoviny', nativeName: 'Côte d\'Ivoire', flag: '🇨🇮' },
  { code: '+226', country: 'Burkina Faso', nativeName: 'Burkina Faso', flag: '🇧🇫' },
  { code: '+227', country: 'Niger', nativeName: 'Niger', flag: '🇳🇪' },
  { code: '+228', country: 'Togo', nativeName: 'Togo', flag: '🇹🇬' },
  { code: '+229', country: 'Benin', nativeName: 'Bénin', flag: '🇧🇯' },
  { code: '+230', country: 'Mauricius', nativeName: 'Maurice', flag: '🇲🇺' },
  { code: '+231', country: 'Libérie', nativeName: 'Liberia', flag: '🇱🇷' },
  { code: '+232', country: 'Sierra Leone', nativeName: 'Sierra Leone', flag: '🇸🇱' },
  { code: '+233', country: 'Ghana', nativeName: 'Ghana', flag: '🇬🇭' },
  { code: '+234', country: 'Nigérie', nativeName: 'Nigeria', flag: '🇳🇬' },
  { code: '+235', country: 'Čad', nativeName: 'Tchad', flag: '🇹🇩' },
  { code: '+236', country: 'Středoafrická republika', nativeName: 'République centrafricaine', flag: '🇨🇫' },
  { code: '+237', country: 'Kamerun', nativeName: 'Cameroun', flag: '🇨🇲' },
  { code: '+238', country: 'Kapverdy', nativeName: 'Cabo Verde', flag: '🇨🇻' },
  { code: '+239', country: 'Svatý Tomáš a Princův ostrov', nativeName: 'São Tomé e Príncipe', flag: '🇸🇹' },
  { code: '+240', country: 'Rovníková Guinea', nativeName: 'Guinea Ecuatorial', flag: '🇬🇶' },
  { code: '+241', country: 'Gabon', nativeName: 'Gabon', flag: '🇬🇦' },
  { code: '+242', country: 'Republika Kongo', nativeName: 'Congo', flag: '🇨🇬' },
  { code: '+243', country: 'Demokratická republika Kongo', nativeName: 'Congo', flag: '🇨🇩' },
  { code: '+244', country: 'Angola', nativeName: 'Angola', flag: '🇦🇴' },
  { code: '+245', country: 'Guinea-Bissau', nativeName: 'Guiné-Bissau', flag: '🇬🇼' },
  { code: '+246', country: 'Britské indickooceánské území', nativeName: 'British Indian Ocean Territory', flag: '🇮🇴' },
  { code: '+248', country: 'Seychely', nativeName: 'Seychelles', flag: '🇸🇨' },
  { code: '+249', country: 'Súdán', nativeName: 'السودان', flag: '🇸🇩' },
  { code: '+250', country: 'Rwanda', nativeName: 'Rwanda', flag: '🇷🇼' },
  { code: '+251', country: 'Etiopie', nativeName: 'ኢትዮጵያ', flag: '🇪🇹' },
  { code: '+252', country: 'Somálsko', nativeName: 'Soomaaliya', flag: '🇸🇴' },
  { code: '+253', country: 'Džibutsko', nativeName: 'Djibouti', flag: '🇩🇯' },
  { code: '+254', country: 'Keňa', nativeName: 'Kenya', flag: '🇰🇪' },
  { code: '+255', country: 'Tanzanie', nativeName: 'Tanzania', flag: '🇹🇿' },
  { code: '+256', country: 'Uganda', nativeName: 'Uganda', flag: '🇺🇬' },
  { code: '+257', country: 'Burundi', nativeName: 'Burundi', flag: '🇧🇮' },
  { code: '+258', country: 'Mosambik', nativeName: 'Moçambique', flag: '🇲🇿' },
  { code: '+260', country: 'Zambie', nativeName: 'Zambia', flag: '🇿🇲' },
  { code: '+261', country: 'Madagaskar', nativeName: 'Madagasikara', flag: '🇲🇬' },
  { code: '+262', country: 'Réunion', nativeName: 'La Réunion', flag: '🇷🇪' },
  { code: '+263', country: 'Zimbabwe', nativeName: 'Zimbabwe', flag: '🇿🇼' },
  { code: '+264', country: 'Namibie', nativeName: 'Namibia', flag: '🇳🇦' },
  { code: '+265', country: 'Malawi', nativeName: 'Malawi', flag: '🇲🇼' },
  { code: '+266', country: 'Lesotho', nativeName: 'Lesotho', flag: '🇱🇸' },
  { code: '+267', country: 'Botswana', nativeName: 'Botswana', flag: '🇧🇼' },
  { code: '+268', country: 'Eswatini', nativeName: 'Eswatini', flag: '🇸🇿' },
  { code: '+269', country: 'Komory', nativeName: 'Comores', flag: '🇰🇲' },
  { code: '+290', country: 'Svatá Helena', nativeName: 'Saint Helena', flag: '🇸🇭' },
  { code: '+291', country: 'Eritrea', nativeName: 'ኤርትራ', flag: '🇪🇷' },
  { code: '+297', country: 'Aruba', nativeName: 'Aruba', flag: '🇦🇼' },
  { code: '+298', country: 'Faerské ostrovy', nativeName: 'Føroyar', flag: '🇫🇴' },
  { code: '+299', country: 'Grónsko', nativeName: 'Kalaallit Nunaat', flag: '🇬🇱' },
  { code: '+350', country: 'Gibraltar', nativeName: 'Gibraltar', flag: '🇬🇮' },
  { code: '+351', country: 'Portugalsko', nativeName: 'Portugal', flag: '🇵🇹' },
  { code: '+352', country: 'Lucembursko', nativeName: 'Luxembourg', flag: '🇱🇺' },
  { code: '+353', country: 'Irsko', nativeName: 'Éire', flag: '🇮🇪' },
  { code: '+354', country: 'Island', nativeName: 'Ísland', flag: '🇮🇸' },
  { code: '+355', country: 'Albánie', nativeName: 'Shqipëria', flag: '🇦🇱' },
  { code: '+356', country: 'Malta', nativeName: 'Malta', flag: '🇲🇹' },
  { code: '+357', country: 'Kypr', nativeName: 'Κύπρος', flag: '🇨🇾' },
  { code: '+358', country: 'Finsko', nativeName: 'Suomi', flag: '🇫🇮' },
  { code: '+359', country: 'Bulharsko', nativeName: 'България', flag: '🇧🇬' },
  { code: '+370', country: 'Litva', nativeName: 'Lietuva', flag: '🇱🇹' },
  { code: '+371', country: 'Lotyšsko', nativeName: 'Latvija', flag: '🇱🇻' },
  { code: '+372', country: 'Estonsko', nativeName: 'Eesti', flag: '🇪🇪' },
  { code: '+373', country: 'Moldavsko', nativeName: 'Moldova', flag: '🇲🇩' },
  { code: '+374', country: 'Arménie', nativeName: 'Հայաստան', flag: '🇦🇲' },
  { code: '+375', country: 'Bělorusko', nativeName: 'Беларусь', flag: '🇧🇾' },
  { code: '+376', country: 'Andorra', nativeName: 'Andorra', flag: '🇦🇩' },
  { code: '+377', country: 'Monako', nativeName: 'Monaco', flag: '🇲🇨' },
  { code: '+378', country: 'San Marino', nativeName: 'San Marino', flag: '🇸🇲' },
  { code: '+380', country: 'Ukrajina', nativeName: 'Україна', flag: '🇺🇦' },
  { code: '+381', country: 'Srbsko', nativeName: 'Србија', flag: '🇷🇸' },
  { code: '+382', country: 'Černá Hora', nativeName: 'Crna Gora', flag: '🇲🇪' },
  { code: '+383', country: 'Kosovo', nativeName: 'Kosova', flag: '🇽🇰' },
  { code: '+385', country: 'Chorvatsko', nativeName: 'Hrvatska', flag: '🇭🇷' },
  { code: '+386', country: 'Slovinsko', nativeName: 'Slovenija', flag: '🇸🇮' },
  { code: '+387', country: 'Bosna a Hercegovina', nativeName: 'Bosna i Hercegovina', flag: '🇧🇦' },
  { code: '+389', country: 'Severní Makedonie', nativeName: 'Северна Македонија', flag: '🇲🇰' },
  { code: '+420', country: 'Česká republika', nativeName: 'Česká republika', flag: '🇨🇿' },
  { code: '+421', country: 'Slovensko', nativeName: 'Slovensko', flag: '🇸🇰' },
  { code: '+423', country: 'Lichtenštejnsko', nativeName: 'Liechtenstein', flag: '🇱🇮' },
  { code: '+500', country: 'Falklandské ostrovy', nativeName: 'Falkland Islands', flag: '🇫🇰' },
  { code: '+501', country: 'Belize', nativeName: 'Belize', flag: '🇧🇿' },
  { code: '+502', country: 'Guatemala', nativeName: 'Guatemala', flag: '🇬🇹' },
  { code: '+503', country: 'El Salvador', nativeName: 'El Salvador', flag: '🇸🇻' },
  { code: '+504', country: 'Honduras', nativeName: 'Honduras', flag: '🇭🇳' },
  { code: '+505', country: 'Nikaragua', nativeName: 'Nicaragua', flag: '🇳🇮' },
  { code: '+506', country: 'Kostarika', nativeName: 'Costa Rica', flag: '🇨🇷' },
  { code: '+507', country: 'Panama', nativeName: 'Panamá', flag: '🇵🇦' },
  { code: '+508', country: 'Svatý Pierre a Miquelon', nativeName: 'Saint-Pierre-et-Miquelon', flag: '🇵🇲' },
  { code: '+509', country: 'Haiti', nativeName: 'Haïti', flag: '🇭🇹' },
  { code: '+590', country: 'Guadeloupe', nativeName: 'Guadeloupe', flag: '🇬🇵' },
  { code: '+591', country: 'Bolívie', nativeName: 'Bolivia', flag: '🇧🇴' },
  { code: '+592', country: 'Guyana', nativeName: 'Guyana', flag: '🇬🇾' },
  { code: '+593', country: 'Ekvádor', nativeName: 'Ecuador', flag: '🇪🇨' },
  { code: '+594', country: 'Francouzská Guyana', nativeName: 'Guyane', flag: '🇬🇫' },
  { code: '+595', country: 'Paraguay', nativeName: 'Paraguay', flag: '🇵🇾' },
  { code: '+596', country: 'Martinik', nativeName: 'Martinique', flag: '🇲🇶' },
  { code: '+597', country: 'Surinam', nativeName: 'Suriname', flag: '🇸🇷' },
  { code: '+598', country: 'Uruguay', nativeName: 'Uruguay', flag: '🇺🇾' },
  { code: '+599', country: 'Curaçao', nativeName: 'Curaçao', flag: '🇨🇼' },
  { code: '+670', country: 'Východní Timor', nativeName: 'Timor-Leste', flag: '🇹🇱' },
  { code: '+672', country: 'Antarktida', nativeName: 'Antarctica', flag: '🇦🇶' },
  { code: '+673', country: 'Brunej', nativeName: 'Brunei', flag: '🇧🇳' },
  { code: '+674', country: 'Nauru', nativeName: 'Nauru', flag: '🇳🇷' },
  { code: '+675', country: 'Papua-Nová Guinea', nativeName: 'Papua New Guinea', flag: '🇵🇬' },
  { code: '+676', country: 'Tonga', nativeName: 'Tonga', flag: '🇹🇴' },
  { code: '+677', country: 'Šalamounovy ostrovy', nativeName: 'Solomon Islands', flag: '🇸🇧' },
  { code: '+678', country: 'Vanuatu', nativeName: 'Vanuatu', flag: '🇻🇺' },
  { code: '+679', country: 'Fidži', nativeName: 'Fiji', flag: '🇫🇯' },
  { code: '+680', country: 'Palau', nativeName: 'Palau', flag: '🇵🇼' },
  { code: '+681', country: 'Wallis a Futuna', nativeName: 'Wallis-et-Futuna', flag: '🇼🇫' },
  { code: '+682', country: 'Cookovy ostrovy', nativeName: 'Cook Islands', flag: '🇨🇰' },
  { code: '+683', country: 'Niue', nativeName: 'Niue', flag: '🇳🇺' },
  { code: '+685', country: 'Samoa', nativeName: 'Samoa', flag: '🇼🇸' },
  { code: '+686', country: 'Kiribati', nativeName: 'Kiribati', flag: '🇰🇮' },
  { code: '+687', country: 'Nová Kaledonie', nativeName: 'Nouvelle-Calédonie', flag: '🇳🇨' },
  { code: '+688', country: 'Tuvalu', nativeName: 'Tuvalu', flag: '🇹🇻' },
  { code: '+689', country: 'Francouzská Polynésie', nativeName: 'Polynésie française', flag: '🇵🇫' },
  { code: '+690', country: 'Tokelau', nativeName: 'Tokelau', flag: '🇹🇰' },
  { code: '+691', country: 'Mikronésie', nativeName: 'Micronesia', flag: '🇫🇲' },
  { code: '+692', country: 'Marshallovy ostrovy', nativeName: 'Marshall Islands', flag: '🇲🇭' },
  { code: '+850', country: 'Severní Korea', nativeName: '북한', flag: '🇰🇵' },
  { code: '+852', country: 'Hongkong', nativeName: '香港', flag: '🇭🇰' },
  { code: '+853', country: 'Macao', nativeName: '澳門', flag: '🇲🇴' },
  { code: '+855', country: 'Kambodža', nativeName: 'កម្ពុជា', flag: '🇰🇭' },
  { code: '+856', country: 'Laos', nativeName: 'ລາວ', flag: '🇱🇦' },
  { code: '+880', country: 'Bangladéš', nativeName: 'বাংলাদেশ', flag: '🇧🇩' },
  { code: '+886', country: 'Tchaj-wan', nativeName: '台灣', flag: '🇹🇼' },
  { code: '+960', country: 'Maledivy', nativeName: 'ދިވެހިރާއްޖެ', flag: '🇲🇻' },
  { code: '+961', country: 'Libanon', nativeName: 'لبنان', flag: '🇱🇧' },
  { code: '+962', country: 'Jordánsko', nativeName: 'الأردن', flag: '🇯🇴' },
  { code: '+963', country: 'Sýrie', nativeName: 'سوريا', flag: '🇸🇾' },
  { code: '+964', country: 'Irák', nativeName: 'العراق', flag: '🇮🇶' },
  { code: '+965', country: 'Kuvajt', nativeName: 'الكويت', flag: '🇰🇼' },
  { code: '+966', country: 'Saúdská Arábie', nativeName: 'السعودية', flag: '🇸🇦' },
  { code: '+967', country: 'Jemen', nativeName: 'اليمن', flag: '🇾🇪' },
  { code: '+968', country: 'Omán', nativeName: 'عمان', flag: '🇴🇲' },
  { code: '+970', country: 'Palestina', nativeName: 'فلسطين', flag: '🇵🇸' },
  { code: '+971', country: 'Spojené arabské emiráty', nativeName: 'الإمارات', flag: '🇦🇪' },
  { code: '+972', country: 'Izrael', nativeName: 'ישראל', flag: '🇮🇱' },
  { code: '+973', country: 'Bahrajn', nativeName: 'البحرين', flag: '🇧🇭' },
  { code: '+974', country: 'Katar', nativeName: 'قطر', flag: '🇶🇦' },
  { code: '+975', country: 'Bhútán', nativeName: 'འབྲུག', flag: '🇧🇹' },
  { code: '+976', country: 'Mongolsko', nativeName: 'Монгол', flag: '🇲🇳' },
  { code: '+977', country: 'Nepál', nativeName: 'नेपाल', flag: '🇳🇵' },
  { code: '+992', country: 'Tádžikistán', nativeName: 'Тоҷикистон', flag: '🇹🇯' },
  { code: '+993', country: 'Turkmenistán', nativeName: 'Türkmenistan', flag: '🇹🇲' },
  { code: '+994', country: 'Ázerbájdžán', nativeName: 'Azərbaycan', flag: '🇦🇿' },
  { code: '+995', country: 'Gruzie', nativeName: 'საქართველო', flag: '🇬🇪' },
  { code: '+996', country: 'Kyrgyzstán', nativeName: 'Кыргызстан', flag: '🇰🇬' },
  { code: '+998', country: 'Uzbekistán', nativeName: 'Oʻzbekiston', flag: '🇺🇿' }
];


// Lokální úložiště
const recentCodesKey = 'recentCountryCodes';
const maxRecent = 5;


initValues();
renderDropdown();


/**
 * Zpracuje kliknutí na možnost předvolby země v dropdownu.
 * @function
 * @param {Event} event - Událost kliknutí.
 * @returns {boolean} True, pokud bylo kliknutí zpracováno.
 */
export function phoneInputClickListeners(event) {
  const countryCodeOption = event.target.closest('.country-code-option');
  if (countryCodeOption) {
    const selectedCode = countryCodeOption.dataset.code;
    changeSelectedCode(selectedCode);
    saveRecentCode(selectedCode);
    const prevActive = document.querySelector('.country-code-option.active');
    prevActive?.classList.remove('active');
    if (!countryCodeOption) {
      countryCodeOption = document.querySelector('#country-code-input');
    }
    countryCodeOption?.classList.add('active');
    const dropdown = document.querySelector('.country-code-dropdown');
    dropdown?.classList.remove('active');
    return true;
  }

  return false;
}


/**
 * Zpracuje vstup do pole pro předvolbu země (input).
 * @function
 * @param {Event} event - Událost vstupu.
 * @returns {boolean} True, pokud byl vstup zpracován.
 */
export function phoneInputInputisteners(event) {
  if (event.target.matches('#country-code-input')) {
    const countryCodeInput = event.target;
    countryCodeInput.value = countryCodeInput.value.trim();
    renderDropdown();
    const dropdown = document.querySelector('.country-code-dropdown');
    dropdown?.classList.add('active');
    return true;
  }
  return false;
}

// focusout listener (dropdown.classList.remove('active')) tu není schválně (nešlo by kliknout na dropdown)

/**
 * Zpracuje focusin na kontejner předvolby země, aktivuje dropdown.
 * @function
 * @param {Event} event - Událost focusin.
 * @returns {boolean} True, pokud byl focusin zpracován.
 */
export function phoneInputFocusinisteners(event) {
  const countryCodeContainer = event.target.closest('.country-code-container');
  if (countryCodeContainer) {
    const dropdown = document.querySelector('.country-code-dropdown');
    dropdown?.classList.add('active');
    return true;
  }
  return false;
}


/**
 * Zpracuje stisk klávesy v kontejneru předvolby země (šipky, enter, escape).
 * @function
 * @param {KeyboardEvent} event - Událost stisku klávesy.
 * @returns {boolean} True, pokud byla klávesa zpracována.
 */
export function phoneInputKeydownListeners(event) {
  const countryCodeContainer = event.target.closest('.country-code-container');
  if (countryCodeContainer) {
    const dropdown = document.querySelector('.country-code-dropdown');

    if (!dropdown) return false;

    if (event.key === 'Escape') {
      if (dropdown?.classList.contains('active')) {
        dropdown?.classList.remove('active');
        return true;
      }
    }

    let indexDirection;
    if (event.key === 'ArrowDown') indexDirection = 1;
    if (event.key === 'ArrowUp') indexDirection = -1;
    if (indexDirection) {
      event.preventDefault();
      dropdown?.classList.add('active');
      const options = document.querySelectorAll('.country-code-option');
      if (!options || !options.length) return true;

      const activeOption = document.querySelector('.country-code-option.active');

      if (!activeOption) {
        const index = indexDirection === 1 ? 0 : options.length - 1;
        const option = options[index];
        option?.classList.add('active');
        option?.scrollIntoView({ behavior: 'instant', block: 'nearest' });
        return true;
      }

      for (let i = 0; i < options.length; i++) {
        const option = options[i];
        if (option?.classList.contains('active')) {
          option?.classList.remove('active');
          let nextOption = options[i + indexDirection];
          if (!nextOption) nextOption = options[indexDirection === 1 ? 0 : options.length - 1];
          nextOption?.classList.add('active');
          nextOption?.scrollIntoView({ behavior: 'instant', block: 'nearest' });
          return true;
        }
      }
      return true;
    }

    if (event.key === 'Enter') {
      event.preventDefault();
      if (!dropdown?.classList.contains('active')) return true;
      let activeOption = document.querySelector('.country-code-option.active');
      if (!activeOption) {
        const options = document.querySelectorAll('.country-code-option');
        if (options && options.length === 1) {
          activeOption = options[0];
        } else {
          return true;
        }
      }
      changeSelectedCode(activeOption.dataset.code);
      saveRecentCode(activeOption.dataset.code);
      dropdown?.classList.remove('active');
      return true;
    }
  }
  return false;
}


document.addEventListener('click', (event) => {
  const countryCodeContainer = document.querySelector('.country-code-container');
  if (countryCodeContainer && !countryCodeContainer.contains(event.target)) {
    const dropdown = document.querySelector('.country-code-dropdown');
    dropdown?.classList.remove('active');
  }
});



/**
 * Inicializuje hodnoty při načtení (nastaví poslední použitou předvolbu).
 * @function
 */
export function initValues() {
  const recent = getRecentCodes();
  if (recent.length > 0) {
    changeSelectedCode(recent[0]);
  }
}


/**
 * Změní aktuálně vybranou předvolbu země.
 * @function
 * @param {string} code - Nová předvolba (např. '+420').
 */
export function changeSelectedCode(code) {
  const countryCodeInput = document.querySelector('#country-code-input');
  if (countryCodeInput) {
    countryCodeInput.value = code;
    renderDropdown();
  }
}


/**
 * Získá pole naposledy použitých předvoleb ze storage.
 * @function
 * @returns {string[]} Pole předvoleb.
 */
function getRecentCodes() {
  const stored = localStorage.getItem(recentCodesKey);
  return stored ? JSON.parse(stored) : [];
}


/**
 * Uloží předvolbu do seznamu naposledy použitých.
 * @function
 * @param {string} code - Předvolba k uložení.
 */
function saveRecentCode(code) {
  let recent = getRecentCodes();
  recent = recent.filter(c => c !== code);
  recent.unshift(code);
  recent = recent.slice(0, maxRecent);
  localStorage.setItem(recentCodesKey, JSON.stringify(recent));
}


/**
 * Vykreslí dropdown s předvolbami zemí podle aktuálního vstupu a historie.
 * @function
 */
export function renderDropdown() {
  const countryCodeInput = document.querySelector('#country-code-input');
  if (!countryCodeInput) {
    return;
  }
  const dropdownContent = document.querySelector('.dropdown-content');
  if (!dropdownContent) {
    return;
  }

  const recent = getRecentCodes();
  const recentCodes = recent.map(code => countryCodes.find(ac => ac.code === code)).filter(Boolean);
  const searchTerm = countryCodeInput.value.trim();

  let filtered = countryCodes;
  if (searchTerm) {
    const term = searchTerm.toLowerCase();
    filtered = countryCodes.filter(countryCode =>
      countryCode.country.toLowerCase().includes(term) ||
      countryCode.nativeName.toLowerCase().includes(term) ||
      countryCode.code.includes(term)
    );
  }

  let html = '';

  if (recentCodes.length > 0 && !searchTerm) {
    let rcHTML = '';
    recentCodes.forEach(recentCountryCode => {
      rcHTML += `
        <div class="country-code-option ${recentCountryCode.code === countryCodeInput.value ? 'selected' : ''}" data-code="${recentCountryCode.code}">
          <span class="flag">${recentCountryCode.flag}</span>
          <div class="country-info">
            <span class="country-name">${recentCountryCode.country}</span>
            <span class="country-native">${recentCountryCode.nativeName}</span>
          </div>
          <span class="country-code">${recentCountryCode.code}</span>
        </div>
      `;
    });
    html += `
    <div class="country-code-section">
      <div class="section-title">Nedávno použité</div>
      ${rcHTML}
    </div>
    `;
  }

  if (filtered.length > 0) {
    if (recentCodes.length > 0 && !searchTerm) {
      html += '<div class="country-code-section">';
      html += '<div class="section-title">Všechny země</div>';
    }

    filtered.forEach(countryCode => {
      if (recentCodes.some(rc => rc.code === countryCode.code) && !searchTerm) return;

      html += `
        <div class="country-code-option ${countryCode.code === countryCodeInput.value ? 'selected' : ''}" data-code="${countryCode.code}">
          <span class="flag">${countryCode.flag}</span>
          <div class="country-info">
            <span class="country-name">${countryCode.country}</span>
            <span class="country-native">${countryCode.nativeName}</span>
          </div>
          <span class="country-code">${countryCode.code}</span>
        </div>
      `;
    });

    if (recentCodes.length > 0 && !searchTerm) {
      html += '</div>';
    }
  } else {
    html = '<div class="no-results">Žádné výsledky</div>';
  }

  dropdownContent.innerHTML = html;


  const firstOption = document.querySelector('.country-code-option');
  firstOption?.classList.add('active');
}
