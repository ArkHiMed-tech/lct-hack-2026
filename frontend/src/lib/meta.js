export const CATEGORIES = {
  fire: { label: 'Пожар', tone: 'tone-fire' },
  medical: { label: 'Медицина', tone: 'tone-medical' },
  gas: { label: 'Газ', tone: 'tone-gas' },
  dth: { label: 'ДТП', tone: 'tone-dth' },
};

export const DIFFICULTY = {
  easy: { label: 'Лёгкий', tone: 'diff-easy' },
  medium: { label: 'Средний', tone: 'diff-medium' },
  hard: { label: 'Сложный', tone: 'diff-hard' },
};

export const SEVERITY = {
  low: { label: 'Низкая' },
  medium: { label: 'Средняя' },
  high: { label: 'Высокая' },
};

export const STATUS = {
  new: { label: 'Новый', btn: 'Начать' },
  in_progress: { label: 'В процессе', btn: 'Продолжить' },
  done: { label: 'Завершён', btn: 'Повторить' },
};

export const ROLE_LABELS = {
  student: 'Обучающийся',
  teacher: 'Преподаватель',
  admin: 'Администратор',
};

export function categoryLabel(id) {
  return CATEGORIES[id]?.label ?? id;
}

export function formatScore(score) {
  return score == null ? '—' : `${score}%`;
}

export const SERVICES = {
  fire: 'Пожарно-спасательная',
  ambulance: 'Скорая медицинская',
  police: 'Полиция',
  gas: 'Аварийная газовая',
  utility: 'Аварийная городская',
  codd: 'ЦОДД',
  mosbez: 'Московская безопасность',
  moslift: 'Мослифт',
  oati: 'ОАТИ',
};

export function serviceLabel(id) {
  return SERVICES[id] ?? id;
}

const categorySelect = (options, style) => ({
  id: 'incident_category',
  label: 'Категория происшествия',
  kind: 'select',
  options,
  required: true,
});

export const FORM_FIELDS = {
  fire: [
    { id: 'what', label: 'Что произошло? (кратко)', kind: 'text', required: true },
    categorySelect(['fire', 'medical', 'gas', 'dth']),
    { id: 'address', label: 'Точный адрес: город, улица, дом, квартира', kind: 'text', required: true },
    { id: 'time', label: 'Когда произошло?', kind: 'text', required: true },
    { id: 'caller_name', label: 'ФИО звонящего', kind: 'text', required: true },
    { id: 'victims', label: 'Число пострадавших', kind: 'text', required: true },
    { id: 'conditions', label: 'Состояние пострадавших', kind: 'text', required: true },
    { id: 'threat', label: 'Угроза жизни?', kind: 'select', options: ['Да', 'Нет', 'Неясно'], required: true },
    {
      id: 'factors',
      label: 'Опасные факторы',
      kind: 'multi',
      options: ['Открытое пламя', 'Дым', 'Запах газа', 'Разлив опасных веществ', 'Угроза обрушения'],
      required: true,
    },
    { id: 'actions', label: 'Что предпринял абонент?', kind: 'text', required: true },
    { id: 'landmarks', label: 'Ориентиры / пути подъезда', kind: 'text' },
  ],
  medical: [
    { id: 'what', label: 'Что произошло? (кратко)', kind: 'text', required: true },
    categorySelect(['fire', 'medical', 'gas', 'dth']),
    { id: 'address', label: 'Точный адрес: город, улица, дом, квартира', kind: 'text', required: true },
    { id: 'time', label: 'Когда произошло?', kind: 'text', required: true },
    { id: 'caller_name', label: 'ФИО звонящего', kind: 'text', required: true },
    { id: 'victims', label: 'Число пострадавших', kind: 'text', required: true },
    { id: 'conditions', label: 'Состояние: сознание, дыхание', kind: 'text', required: true },
    { id: 'threat', label: 'Угроза жизни?', kind: 'select', options: ['Да', 'Нет', 'Неясно'], required: true },
    { id: 'actions', label: 'Что предпринимает абонент?', kind: 'text', required: true },
  ],
  gas: [
    { id: 'what', label: 'Что произошло? (кратко)', kind: 'text', required: true },
    categorySelect(['fire', 'medical', 'gas', 'dth']),
    { id: 'address', label: 'Точный адрес: город, улица, дом', kind: 'text', required: true },
    { id: 'time', label: 'Когда обнаружено?', kind: 'text', required: true },
    { id: 'caller_name', label: 'ФИО звонящего', kind: 'text', required: true },
    { id: 'victims', label: 'Есть ли пострадавшие от газа?', kind: 'text', required: true },
    { id: 'threat', label: 'Риск возгорания?', kind: 'select', options: ['Да', 'Нет', 'Неясно'], required: true },
    {
      id: 'factors',
      label: 'Опасные факторы',
      kind: 'multi',
      options: ['Запах газа', 'Открытый огонь рядом', 'Пользовались лифтом'],
      required: true,
    },
    { id: 'actions', label: 'Что уже сделано?', kind: 'text', required: true },
  ],
  dth: [
    { id: 'what', label: 'Что произошло? (кратко)', kind: 'text', required: true },
    categorySelect(['fire', 'medical', 'gas', 'dth']),
    { id: 'address', label: 'Точное место: проспект/улица, дом, ориентир', kind: 'text', required: true },
    { id: 'time', label: 'Когда случилось?', kind: 'text', required: true },
    { id: 'caller_name', label: 'ФИО звонящего', kind: 'text', required: true },
    { id: 'victims', label: 'Число пострадавших', kind: 'text', required: true },
    { id: 'conditions', label: 'Состояние: сознание, травмы', kind: 'text', required: true },
    { id: 'threat', label: 'Угроза жизни?', kind: 'select', options: ['Да', 'Нет', 'Неясно'], required: true },
    {
      id: 'factors',
      label: 'Опасные факторы',
      kind: 'multi',
      options: ['Утечка топлива', 'Риск возгорания', 'Зажаты люди', 'Пробка'],
      required: true,
    },
    { id: 'actions', label: 'Что предпринято?', kind: 'text', required: true },
  ],
};

export function getFormFields(scenario) {
  const fields = FORM_FIELDS[scenario?.category] ?? FORM_FIELDS.fire;
  const requiredIds = scenario?.required_fields ?? [];
  return fields.filter((f) => requiredIds.includes(f.id)).map((f) => ({
    ...f,
    required: requiredIds.includes(f.id),
  }));
}

export const VERDICT_LABELS = {
  excellent: 'Зачтено · отлично',
  pass: 'Зачтено',
  fail: 'Не зачтено',
};