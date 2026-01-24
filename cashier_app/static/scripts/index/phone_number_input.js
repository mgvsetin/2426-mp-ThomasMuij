const countryCodes = [
  { code: '', country: 'Žádné', nativeName: 'Žádné předčíslí', flag: '' },
  { code: '+1', country: 'USA / Canada', nativeName: 'USA / Canada', flag: '🇺🇸' },
  { code: '+7', country: 'Russia', nativeName: 'Россия', flag: '🇷🇺' },
  { code: '+20', country: 'Egypt', nativeName: 'مصر', flag: '🇪🇬' },
  { code: '+27', country: 'South Africa', nativeName: 'South Africa', flag: '🇿🇦' },
  { code: '+30', country: 'Greece', nativeName: 'Ελλάδα', flag: '🇬🇷' },
  { code: '+31', country: 'Netherlands', nativeName: 'Nederland', flag: '🇳🇱' },
  { code: '+32', country: 'Belgium', nativeName: 'België / Belgique', flag: '🇧🇪' },
  { code: '+33', country: 'France', nativeName: 'France', flag: '🇫🇷' },
  { code: '+34', country: 'Spain', nativeName: 'España', flag: '🇪🇸' },
  { code: '+36', country: 'Hungary', nativeName: 'Magyarország', flag: '🇭🇺' },
  { code: '+39', country: 'Italy', nativeName: 'Italia', flag: '🇮🇹' },
  { code: '+40', country: 'Romania', nativeName: 'România', flag: '🇷🇴' },
  { code: '+41', country: 'Switzerland', nativeName: 'Schweiz / Suisse', flag: '🇨🇭' },
  { code: '+43', country: 'Austria', nativeName: 'Österreich', flag: '🇦🇹' },
  { code: '+44', country: 'United Kingdom', nativeName: 'United Kingdom', flag: '🇬🇧' },
  { code: '+45', country: 'Denmark', nativeName: 'Danmark', flag: '🇩🇰' },
  { code: '+46', country: 'Sweden', nativeName: 'Sverige', flag: '🇸🇪' },
  { code: '+47', country: 'Norway', nativeName: 'Norge', flag: '🇳🇴' },
  { code: '+48', country: 'Poland', nativeName: 'Polska', flag: '🇵🇱' },
  { code: '+49', country: 'Germany', nativeName: 'Deutschland', flag: '🇩🇪' },
  { code: '+51', country: 'Peru', nativeName: 'Perú', flag: '🇵🇪' },
  { code: '+52', country: 'Mexico', nativeName: 'México', flag: '🇲🇽' },
  { code: '+53', country: 'Cuba', nativeName: 'Cuba', flag: '🇨🇺' },
  { code: '+54', country: 'Argentina', nativeName: 'Argentina', flag: '🇦🇷' },
  { code: '+55', country: 'Brazil', nativeName: 'Brasil', flag: '🇧🇷' },
  { code: '+56', country: 'Chile', nativeName: 'Chile', flag: '🇨🇱' },
  { code: '+57', country: 'Colombia', nativeName: 'Colombia', flag: '🇨🇴' },
  { code: '+58', country: 'Venezuela', nativeName: 'Venezuela', flag: '🇻🇪' },
  { code: '+60', country: 'Malaysia', nativeName: 'Malaysia', flag: '🇲🇾' },
  { code: '+61', country: 'Australia', nativeName: 'Australia', flag: '🇦🇺' },
  { code: '+62', country: 'Indonesia', nativeName: 'Indonesia', flag: '🇮🇩' },
  { code: '+63', country: 'Philippines', nativeName: 'Pilipinas', flag: '🇵🇭' },
  { code: '+64', country: 'New Zealand', nativeName: 'New Zealand', flag: '🇳🇿' },
  { code: '+65', country: 'Singapore', nativeName: 'Singapore', flag: '🇸🇬' },
  { code: '+66', country: 'Thailand', nativeName: 'ประเทศไทย', flag: '🇹🇭' },
  { code: '+81', country: 'Japan', nativeName: '日本', flag: '🇯🇵' },
  { code: '+82', country: 'South Korea', nativeName: '대한민국', flag: '🇰🇷' },
  { code: '+84', country: 'Vietnam', nativeName: 'Việt Nam', flag: '🇻🇳' },
  { code: '+86', country: 'China', nativeName: '中国', flag: '🇨🇳' },
  { code: '+90', country: 'Turkey', nativeName: 'Türkiye', flag: '🇹🇷' },
  { code: '+91', country: 'India', nativeName: 'भारत', flag: '🇮🇳' },
  { code: '+92', country: 'Pakistan', nativeName: 'پاکستان', flag: '🇵🇰' },
  { code: '+93', country: 'Afghanistan', nativeName: 'افغانستان', flag: '🇦🇫' },
  { code: '+94', country: 'Sri Lanka', nativeName: 'ශ්‍රී ලංකා', flag: '🇱🇰' },
  { code: '+95', country: 'Myanmar', nativeName: 'မြန်မာ', flag: '🇲🇲' },
  { code: '+98', country: 'Iran', nativeName: 'ایران', flag: '🇮🇷' },
  { code: '+211', country: 'South Sudan', nativeName: 'South Sudan', flag: '🇸🇸' },
  { code: '+212', country: 'Morocco', nativeName: 'المغرب', flag: '🇲🇦' },
  { code: '+213', country: 'Algeria', nativeName: 'الجزائر', flag: '🇩🇿' },
  { code: '+216', country: 'Tunisia', nativeName: 'تونس', flag: '🇹🇳' },
  { code: '+218', country: 'Libya', nativeName: 'ليبيا', flag: '🇱🇾' },
  { code: '+220', country: 'Gambia', nativeName: 'Gambia', flag: '🇬🇲' },
  { code: '+221', country: 'Senegal', nativeName: 'Sénégal', flag: '🇸🇳' },
  { code: '+222', country: 'Mauritania', nativeName: 'موريتانيا', flag: '🇲🇷' },
  { code: '+223', country: 'Mali', nativeName: 'Mali', flag: '🇲🇱' },
  { code: '+224', country: 'Guinea', nativeName: 'Guinée', flag: '🇬🇳' },
  { code: '+225', country: 'Ivory Coast', nativeName: 'Côte d\'Ivoire', flag: '🇨🇮' },
  { code: '+226', country: 'Burkina Faso', nativeName: 'Burkina Faso', flag: '🇧🇫' },
  { code: '+227', country: 'Niger', nativeName: 'Niger', flag: '🇳🇪' },
  { code: '+228', country: 'Togo', nativeName: 'Togo', flag: '🇹🇬' },
  { code: '+229', country: 'Benin', nativeName: 'Bénin', flag: '🇧🇯' },
  { code: '+230', country: 'Mauritius', nativeName: 'Maurice', flag: '🇲🇺' },
  { code: '+231', country: 'Liberia', nativeName: 'Liberia', flag: '🇱🇷' },
  { code: '+232', country: 'Sierra Leone', nativeName: 'Sierra Leone', flag: '🇸🇱' },
  { code: '+233', country: 'Ghana', nativeName: 'Ghana', flag: '🇬🇭' },
  { code: '+234', country: 'Nigeria', nativeName: 'Nigeria', flag: '🇳🇬' },
  { code: '+235', country: 'Chad', nativeName: 'Tchad', flag: '🇹🇩' },
  { code: '+236', country: 'Central African Republic', nativeName: 'République centrafricaine', flag: '🇨🇫' },
  { code: '+237', country: 'Cameroon', nativeName: 'Cameroun', flag: '🇨🇲' },
  { code: '+238', country: 'Cape Verde', nativeName: 'Cabo Verde', flag: '🇨🇻' },
  { code: '+239', country: 'São Tomé and Príncipe', nativeName: 'São Tomé e Príncipe', flag: '🇸🇹' },
  { code: '+240', country: 'Equatorial Guinea', nativeName: 'Guinea Ecuatorial', flag: '🇬🇶' },
  { code: '+241', country: 'Gabon', nativeName: 'Gabon', flag: '🇬🇦' },
  { code: '+242', country: 'Republic of the Congo', nativeName: 'Congo', flag: '🇨🇬' },
  { code: '+243', country: 'Democratic Republic of the Congo', nativeName: 'Congo', flag: '🇨🇩' },
  { code: '+244', country: 'Angola', nativeName: 'Angola', flag: '🇦🇴' },
  { code: '+245', country: 'Guinea-Bissau', nativeName: 'Guiné-Bissau', flag: '🇬🇼' },
  { code: '+246', country: 'British Indian Ocean Territory', nativeName: 'British Indian Ocean Territory', flag: '🇮🇴' },
  { code: '+248', country: 'Seychelles', nativeName: 'Seychelles', flag: '🇸🇨' },
  { code: '+249', country: 'Sudan', nativeName: 'السودان', flag: '🇸🇩' },
  { code: '+250', country: 'Rwanda', nativeName: 'Rwanda', flag: '🇷🇼' },
  { code: '+251', country: 'Ethiopia', nativeName: 'ኢትዮጵያ', flag: '🇪🇹' },
  { code: '+252', country: 'Somalia', nativeName: 'Soomaaliya', flag: '🇸🇴' },
  { code: '+253', country: 'Djibouti', nativeName: 'Djibouti', flag: '🇩🇯' },
  { code: '+254', country: 'Kenya', nativeName: 'Kenya', flag: '🇰🇪' },
  { code: '+255', country: 'Tanzania', nativeName: 'Tanzania', flag: '🇹🇿' },
  { code: '+256', country: 'Uganda', nativeName: 'Uganda', flag: '🇺🇬' },
  { code: '+257', country: 'Burundi', nativeName: 'Burundi', flag: '🇧🇮' },
  { code: '+258', country: 'Mozambique', nativeName: 'Moçambique', flag: '🇲🇿' },
  { code: '+260', country: 'Zambia', nativeName: 'Zambia', flag: '🇿🇲' },
  { code: '+261', country: 'Madagascar', nativeName: 'Madagasikara', flag: '🇲🇬' },
  { code: '+262', country: 'Réunion', nativeName: 'La Réunion', flag: '🇷🇪' },
  { code: '+263', country: 'Zimbabwe', nativeName: 'Zimbabwe', flag: '🇿🇼' },
  { code: '+264', country: 'Namibia', nativeName: 'Namibia', flag: '🇳🇦' },
  { code: '+265', country: 'Malawi', nativeName: 'Malawi', flag: '🇲🇼' },
  { code: '+266', country: 'Lesotho', nativeName: 'Lesotho', flag: '🇱🇸' },
  { code: '+267', country: 'Botswana', nativeName: 'Botswana', flag: '🇧🇼' },
  { code: '+268', country: 'Eswatini', nativeName: 'Eswatini', flag: '🇸🇿' },
  { code: '+269', country: 'Comoros', nativeName: 'Comores', flag: '🇰🇲' },
  { code: '+290', country: 'Saint Helena', nativeName: 'Saint Helena', flag: '🇸🇭' },
  { code: '+291', country: 'Eritrea', nativeName: 'ኤርትራ', flag: '🇪🇷' },
  { code: '+297', country: 'Aruba', nativeName: 'Aruba', flag: '🇦🇼' },
  { code: '+298', country: 'Faroe Islands', nativeName: 'Føroyar', flag: '🇫🇴' },
  { code: '+299', country: 'Greenland', nativeName: 'Kalaallit Nunaat', flag: '🇬🇱' },
  { code: '+350', country: 'Gibraltar', nativeName: 'Gibraltar', flag: '🇬🇮' },
  { code: '+351', country: 'Portugal', nativeName: 'Portugal', flag: '🇵🇹' },
  { code: '+352', country: 'Luxembourg', nativeName: 'Luxembourg', flag: '🇱🇺' },
  { code: '+353', country: 'Ireland', nativeName: 'Éire', flag: '🇮🇪' },
  { code: '+354', country: 'Iceland', nativeName: 'Ísland', flag: '🇮🇸' },
  { code: '+355', country: 'Albania', nativeName: 'Shqipëria', flag: '🇦🇱' },
  { code: '+356', country: 'Malta', nativeName: 'Malta', flag: '🇲🇹' },
  { code: '+357', country: 'Cyprus', nativeName: 'Κύπρος', flag: '🇨🇾' },
  { code: '+358', country: 'Finland', nativeName: 'Suomi', flag: '🇫🇮' },
  { code: '+359', country: 'Bulgaria', nativeName: 'България', flag: '🇧🇬' },
  { code: '+370', country: 'Lithuania', nativeName: 'Lietuva', flag: '🇱🇹' },
  { code: '+371', country: 'Latvia', nativeName: 'Latvija', flag: '🇱🇻' },
  { code: '+372', country: 'Estonia', nativeName: 'Eesti', flag: '🇪🇪' },
  { code: '+373', country: 'Moldova', nativeName: 'Moldova', flag: '🇲🇩' },
  { code: '+374', country: 'Armenia', nativeName: 'Հայաստան', flag: '🇦🇲' },
  { code: '+375', country: 'Belarus', nativeName: 'Беларусь', flag: '🇧🇾' },
  { code: '+376', country: 'Andorra', nativeName: 'Andorra', flag: '🇦🇩' },
  { code: '+377', country: 'Monaco', nativeName: 'Monaco', flag: '🇲🇨' },
  { code: '+378', country: 'San Marino', nativeName: 'San Marino', flag: '🇸🇲' },
  { code: '+380', country: 'Ukraine', nativeName: 'Україна', flag: '🇺🇦' },
  { code: '+381', country: 'Serbia', nativeName: 'Србија', flag: '🇷🇸' },
  { code: '+382', country: 'Montenegro', nativeName: 'Crna Gora', flag: '🇲🇪' },
  { code: '+383', country: 'Kosovo', nativeName: 'Kosova', flag: '🇽🇰' },
  { code: '+385', country: 'Croatia', nativeName: 'Hrvatska', flag: '🇭🇷' },
  { code: '+386', country: 'Slovenia', nativeName: 'Slovenija', flag: '🇸🇮' },
  { code: '+387', country: 'Bosnia and Herzegovina', nativeName: 'Bosna i Hercegovina', flag: '🇧🇦' },
  { code: '+389', country: 'North Macedonia', nativeName: 'Северна Македонија', flag: '🇲🇰' },
  { code: '+420', country: 'Czech Republic', nativeName: 'Česká republika', flag: '🇨🇿' },
  { code: '+421', country: 'Slovakia', nativeName: 'Slovensko', flag: '🇸🇰' },
  { code: '+423', country: 'Liechtenstein', nativeName: 'Liechtenstein', flag: '🇱🇮' },
  { code: '+500', country: 'Falkland Islands', nativeName: 'Falkland Islands', flag: '🇫🇰' },
  { code: '+501', country: 'Belize', nativeName: 'Belize', flag: '🇧🇿' },
  { code: '+502', country: 'Guatemala', nativeName: 'Guatemala', flag: '🇬🇹' },
  { code: '+503', country: 'El Salvador', nativeName: 'El Salvador', flag: '🇸🇻' },
  { code: '+504', country: 'Honduras', nativeName: 'Honduras', flag: '🇭🇳' },
  { code: '+505', country: 'Nicaragua', nativeName: 'Nicaragua', flag: '🇳🇮' },
  { code: '+506', country: 'Costa Rica', nativeName: 'Costa Rica', flag: '🇨🇷' },
  { code: '+507', country: 'Panama', nativeName: 'Panamá', flag: '🇵🇦' },
  { code: '+508', country: 'Saint Pierre and Miquelon', nativeName: 'Saint-Pierre-et-Miquelon', flag: '🇵🇲' },
  { code: '+509', country: 'Haiti', nativeName: 'Haïti', flag: '🇭🇹' },
  { code: '+590', country: 'Guadeloupe', nativeName: 'Guadeloupe', flag: '🇬🇵' },
  { code: '+591', country: 'Bolivia', nativeName: 'Bolivia', flag: '🇧🇴' },
  { code: '+592', country: 'Guyana', nativeName: 'Guyana', flag: '🇬🇾' },
  { code: '+593', country: 'Ecuador', nativeName: 'Ecuador', flag: '🇪🇨' },
  { code: '+594', country: 'French Guiana', nativeName: 'Guyane', flag: '🇬🇫' },
  { code: '+595', country: 'Paraguay', nativeName: 'Paraguay', flag: '🇵🇾' },
  { code: '+596', country: 'Martinique', nativeName: 'Martinique', flag: '🇲🇶' },
  { code: '+597', country: 'Suriname', nativeName: 'Suriname', flag: '🇸🇷' },
  { code: '+598', country: 'Uruguay', nativeName: 'Uruguay', flag: '🇺🇾' },
  { code: '+599', country: 'Curaçao', nativeName: 'Curaçao', flag: '🇨🇼' },
  { code: '+670', country: 'Timor-Leste', nativeName: 'Timor-Leste', flag: '🇹🇱' },
  { code: '+672', country: 'Antarctica', nativeName: 'Antarctica', flag: '🇦🇶' },
  { code: '+673', country: 'Brunei', nativeName: 'Brunei', flag: '🇧🇳' },
  { code: '+674', country: 'Nauru', nativeName: 'Nauru', flag: '🇳🇷' },
  { code: '+675', country: 'Papua New Guinea', nativeName: 'Papua New Guinea', flag: '🇵🇬' },
  { code: '+676', country: 'Tonga', nativeName: 'Tonga', flag: '🇹🇴' },
  { code: '+677', country: 'Solomon Islands', nativeName: 'Solomon Islands', flag: '🇸🇧' },
  { code: '+678', country: 'Vanuatu', nativeName: 'Vanuatu', flag: '🇻🇺' },
  { code: '+679', country: 'Fiji', nativeName: 'Fiji', flag: '🇫🇯' },
  { code: '+680', country: 'Palau', nativeName: 'Palau', flag: '🇵🇼' },
  { code: '+681', country: 'Wallis and Futuna', nativeName: 'Wallis-et-Futuna', flag: '🇼🇫' },
  { code: '+682', country: 'Cook Islands', nativeName: 'Cook Islands', flag: '🇨🇰' },
  { code: '+683', country: 'Niue', nativeName: 'Niue', flag: '🇳🇺' },
  { code: '+685', country: 'Samoa', nativeName: 'Samoa', flag: '🇼🇸' },
  { code: '+686', country: 'Kiribati', nativeName: 'Kiribati', flag: '🇰🇮' },
  { code: '+687', country: 'New Caledonia', nativeName: 'Nouvelle-Calédonie', flag: '🇳🇨' },
  { code: '+688', country: 'Tuvalu', nativeName: 'Tuvalu', flag: '🇹🇻' },
  { code: '+689', country: 'French Polynesia', nativeName: 'Polynésie française', flag: '🇵🇫' },
  { code: '+690', country: 'Tokelau', nativeName: 'Tokelau', flag: '🇹🇰' },
  { code: '+691', country: 'Micronesia', nativeName: 'Micronesia', flag: '🇫🇲' },
  { code: '+692', country: 'Marshall Islands', nativeName: 'Marshall Islands', flag: '🇲🇭' },
  { code: '+850', country: 'North Korea', nativeName: '북한', flag: '🇰🇵' },
  { code: '+852', country: 'Hong Kong', nativeName: '香港', flag: '🇭🇰' },
  { code: '+853', country: 'Macau', nativeName: '澳門', flag: '🇲🇴' },
  { code: '+855', country: 'Cambodia', nativeName: 'កម្ពុជា', flag: '🇰🇭' },
  { code: '+856', country: 'Laos', nativeName: 'ລາວ', flag: '🇱🇦' },
  { code: '+880', country: 'Bangladesh', nativeName: 'বাংলাদেশ', flag: '🇧🇩' },
  { code: '+886', country: 'Taiwan', nativeName: '台灣', flag: '🇹🇼' },
  { code: '+960', country: 'Maldives', nativeName: 'ދިވެހިރާއްޖެ', flag: '🇲🇻' },
  { code: '+961', country: 'Lebanon', nativeName: 'لبنان', flag: '🇱🇧' },
  { code: '+962', country: 'Jordan', nativeName: 'الأردن', flag: '🇯🇴' },
  { code: '+963', country: 'Syria', nativeName: 'سوريا', flag: '🇸🇾' },
  { code: '+964', country: 'Iraq', nativeName: 'العراق', flag: '🇮🇶' },
  { code: '+965', country: 'Kuwait', nativeName: 'الكويت', flag: '🇰🇼' },
  { code: '+966', country: 'Saudi Arabia', nativeName: 'السعودية', flag: '🇸🇦' },
  { code: '+967', country: 'Yemen', nativeName: 'اليمن', flag: '🇾🇪' },
  { code: '+968', country: 'Oman', nativeName: 'عمان', flag: '🇴🇲' },
  { code: '+970', country: 'Palestine', nativeName: 'فلسطين', flag: '🇵🇸' },
  { code: '+971', country: 'United Arab Emirates', nativeName: 'الإمارات', flag: '🇦🇪' },
  { code: '+972', country: 'Israel', nativeName: 'ישראל', flag: '🇮🇱' },
  { code: '+973', country: 'Bahrain', nativeName: 'البحرين', flag: '🇧🇭' },
  { code: '+974', country: 'Qatar', nativeName: 'قطر', flag: '🇶🇦' },
  { code: '+975', country: 'Bhutan', nativeName: 'འབྲུག', flag: '🇧🇹' },
  { code: '+976', country: 'Mongolia', nativeName: 'Монгол', flag: '🇲🇳' },
  { code: '+977', country: 'Nepal', nativeName: 'नेपाल', flag: '🇳🇵' },
  { code: '+992', country: 'Tajikistan', nativeName: 'Тоҷикистон', flag: '🇹🇯' },
  { code: '+993', country: 'Turkmenistan', nativeName: 'Türkmenistan', flag: '🇹🇲' },
  { code: '+994', country: 'Azerbaijan', nativeName: 'Azərbaycan', flag: '🇦🇿' },
  { code: '+995', country: 'Georgia', nativeName: 'საქართველო', flag: '🇬🇪' },
  { code: '+996', country: 'Kyrgyzstan', nativeName: 'Кыргызстан', flag: '🇰🇬' },
  { code: '+998', country: 'Uzbekistan', nativeName: 'Oʻzbekiston', flag: '🇺🇿' }
];


// LocalStorage
const recentCodesKey = 'recentCountryCodes';
const maxRecent = 5;

const countryCodeContainer = document.querySelector('.country-code-container');
const countryCodeInput = document.querySelector('#country-code-input');
const dropdown = document.querySelector('.country-code-dropdown');
const dropdownContent = document.querySelector('.dropdown-content');


initValues();
renderDropdown();


countryCodeInput.addEventListener('input', async (event) => {
  countryCodeInput.value = countryCodeInput.value.trim();
  renderDropdown();
  dropdown.classList.add('active');
});


countryCodeContainer.addEventListener('focusin', () => {
  dropdown.classList.add('active');
});

// focusout listener (dropdown.classList.remove('active')) tu není schválně (nešlo by kliknout na dropdown)


countryCodeContainer.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    if (dropdown.classList.contains('active')) {
      dropdown.classList.remove('active');
      event.stopPropagation();
    }
  }

  let indexDirection;
  if (event.key === 'ArrowDown') indexDirection = 1;
  if (event.key === 'ArrowUp') indexDirection = -1;
  if (indexDirection) {
    event.preventDefault();
    dropdown.classList.add('active');
    const options = document.querySelectorAll('.country-code-option');
    if (!options.length) return;

    const activeOption = document.querySelector('.country-code-option.active');

    if (!activeOption) {
      const index = indexDirection === 1 ? 0 : options.length - 1;
      const option = options[index];
      option?.classList.add('active');
      option?.scrollIntoView({ behavior: 'instant', block: 'center' });
      return;
    }

    for (let i = 0; i < options.length; i++) {
      const option = options[i];
      if (option.classList.contains('active')) {
        option.classList.remove('active');
        let nextOption = options[i + indexDirection];
        if (!nextOption) nextOption = options[indexDirection === 1 ? 0 : options.length - 1];
        nextOption?.classList.add('active');
        nextOption?.scrollIntoView({ behavior: 'instant', block: 'center' });
        return;
      }
    }
    return;
  }

  if (event.key === 'Enter') {
    event.preventDefault();
    if (!dropdown.classList.contains('active')) return;
    let activeOption = document.querySelector('.country-code-option.active');
    if (!activeOption) {
      const options = document.querySelectorAll('.country-code-option');
      if (options.length === 1) {
        activeOption = options[0];
      } else {
        return;
      }
    }
    changeSelectedCode(activeOption.dataset.code);
    saveRecentCode(activeOption.dataset.code);
    dropdown.classList.remove('active');
    return;
  }
});


export function phoneInputClickListeners(event) {
  const countryCodeOption = event.target.closest('.country-code-option');
  if (countryCodeOption) {
    const selectedCode = countryCodeOption.dataset.code;
    changeSelectedCode(selectedCode);
    saveRecentCode(selectedCode);
    const prevActive = document.querySelector('.country-code-option.active');
    prevActive?.classList.remove('active');
    countryCodeOption.classList.add('active');
    dropdown.classList.remove('active');
    return true;
  }

  return false;
}


document.addEventListener('click', (event) => {
  if (!countryCodeContainer.contains(event.target)) {
    dropdown.classList.remove('active');
  }
});



function initValues() {
  const recent = getRecentCodes();
  if (recent.length > 0) {
    changeSelectedCode(recent[0]);
  }
}


export function changeSelectedCode(code) {
  countryCodeInput.value = code;
  renderDropdown();
}


function getRecentCodes() {
  const stored = localStorage.getItem(recentCodesKey);
  return stored ? JSON.parse(stored) : [];
}


function saveRecentCode(code) {
  let recent = getRecentCodes();
  recent = recent.filter(c => c !== code);
  recent.unshift(code);
  recent = recent.slice(0, maxRecent);
  localStorage.setItem(recentCodesKey, JSON.stringify(recent));
}


function renderDropdown() {
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
