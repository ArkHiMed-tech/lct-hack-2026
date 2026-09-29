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
export const MAIN_SVC_GROUP = { MCHS: '101', Police: '102', AMBULANCE: '103', MOSGAZ: '104' };
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

// Уровни каскада «Что случилось?»: раздел -> Место -> Что -> Проявление -> лист.
// Зеркало backend get_tree_children (дерево грузится с /api/classifier/tree).
export const CASCADE_LEVELS = ['section', 'p1', 'p2', 'p3'];
export const CASCADE_LABELS = { section: 'Раздел', p1: 'Место', p2: 'Что', p3: 'Проявление' };

// Локальный шаг каскада по загруженному дереву.
// path: [{level, value, g?}] (g — только у раздела). Возвращает все варианты
// текущего узла разом + коды листьев, заканчивающихся ровно здесь.
export function walkCascadeTree(tree, path) {
  const roots = tree?.roots ?? [];
  if (!path.length) {
    return {
      breadcrumb: [],
      buttons: roots.map((r) => ({ value: r.title, g: r.g, has_children: true, leaf_count: 0 })),
      selectable: [],
    };
  }
  const [sec, ...rest] = path;
  let node = roots.find((r) => r.g === sec.g) ?? null;
  if (!node) return { breadcrumb: [], buttons: [], selectable: [] };
  const breadcrumb = [{ level: 'section', label: CASCADE_LABELS.section, value: node.title, g: node.g }];
  for (const step of rest) {
    const child = (node.children ?? []).find((c) => c.value === step.value) ?? null;
    if (!child) return { breadcrumb, buttons: [], selectable: [] };
    node = child;
    breadcrumb.push({ level: step.level, label: CASCADE_LABELS[step.level] ?? step.level, value: step.value });
  }
  return {
    breadcrumb,
    buttons: (node.children ?? []).map((c) => ({
      value: c.value,
      has_children: (c.children ?? []).length > 0,
      leaf_count: (c.leaves ?? []).length,
    })),
    selectable: [...(node.leaves ?? [])],
  };
}

// Breadcrumb для листа (раскрытие каскада из поиска/генератора).
export function cascadePathForLeaf(leaf) {
  if (!leaf) return [];
  return [
    { level: 'section', label: CASCADE_LABELS.section, value: leaf.section?.title || '', g: leaf.section?.g },
    ...(leaf.path || []).map((v, i) => ({
      level: CASCADE_LEVELS[i + 1],
      label: CASCADE_LABELS[CASCADE_LEVELS[i + 1]],
      value: v,
    })),
  ];
}
