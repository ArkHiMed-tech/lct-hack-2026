// Типы происшествий карточки 112 — из классификатора (xlsx, граф v2).
//
// Тип происшествия = Итоговый тип классификатора (Номер + путь
// Признак1→Признак2→Признак3), а НЕ номера служб 101/102/103/104.
// Полный индекс листьев грузится с /api/classifier/leaves, здесь —
// локальный поиск, флаги ТЭГов и мелкие справочники.
import {
  SVC_101, SVC_102, SVC_103,
} from './serviceCatalog';

// Инфо-типы без выезда (в классификаторе отсутствуют, разделы 10-23 пустые).
export const QUICK_TYPES = ['Отмена вызова', 'Тестовый вызов', 'Передача дежурства', 'ДТП', 'Консультация', 'Вызов на иностранном языке', 'Ошибочно набран номер', 'Справка 101', 'Справка 102', 'Справка 103'];
// Значимые типы — поисковые подсказки по классификатору.
export const SIGNIFICANT_TYPES = ['ДТП', 'Взрыв', 'Обрушение', 'пожар: мусор', 'запах гари', 'БПЛА'];
// Каналы связи (мок справочника; автоопределение — по префиксу, см. Card112).
export const CHANNELS = ['Теле2', 'МТС', 'Мегафон', 'Билайн', 'Городской', 'SIP', 'Рация', 'Тревожная кнопка'];

// Флаги ТЭГов карточки (колонки-варианты диспетчеризации классификатора).
export const FLAG_DEFS = [
  { key: 'no_access', label: 'Нет доступа (НД)' },
  { key: 'threat', label: 'Угроза людям' },
  { key: 'violation', label: 'Правонарушение' },
  { key: 'medical', label: 'Мед. помощь' },
  { key: 'evac', label: 'Треб. эвакуация' },
  { key: 'gas', label: 'Газификация' },
];
export const EMPTY_FLAGS = { no_access: false, threat: false, violation: false, medical: false, evac: false, gas: false };

// Главная служба классификатора -> группа для подсветки основной службы.
export const MAIN_SVC_GROUP = { MCHS: '101', Police: '102' };
export const MAIN_SVC_NAME = { MCHS: SVC_101, Police: SVC_102, '': '' };

// Нормализация для поиска: нижний регистр, без пунктуации, ё→е.
export function normSearch(s) {
  return String(s ?? '').toLowerCase().replace(/ё/g, 'е').replace(/[‐‑‒–—―.,;:!?()«»"']/g, ' ');
}

// Поиск листьев по подстроке (результат + путь + группа). Зеркало backend search_leaves.
export function searchLeaves(leaves, rawQuery) {
  const tokens = normSearch(rawQuery).split(/\s+/).filter((t) => t.length >= 2);
  if (!tokens.length) return (leaves ?? []).slice(0, 50);
  return (leaves ?? []).filter((leaf) => {
    const hay = normSearch([leaf.result, ...(leaf.path || []), leaf.group].filter(Boolean).join(' '));
    return tokens.every((tok) => hay.includes(tok));
  }).slice(0, 50);
}

// Факторы карточки из листа + флагов (человекочитаемые строки в БД).
export function leafFactors(leaf, flags, tagDesc) {
  const out = (leaf?.path || []).map((part, i) => `Признак${i + 1}: ${part}`);
  const labels = { no_access: 'нет доступа', threat: 'угроза людям', violation: 'правонарушение', medical: 'мед. помощь', evac: 'треб. эвакуация', gas: 'газификация' };
  for (const [key, label] of Object.entries(labels)) {
    if (flags?.[key]) out.push(label);
  }
  if (tagDesc) out.push(tagDesc);
  return out;
}
