// Локальные учётные записи учебного стенда (фронтенд, бэкенд не задействован).
// Логины стилизованы под АРМ ДДС: umc_operdds* — операторы ДДС.
export const ACCOUNTS = [
  {
    login: 'umc_operdds1',
    password: 'dds112-1',
    id: 'u-001',
    name: 'Иванова Мария Петровна',
    last_name: 'Иванова',
    role: 'student',
    post: 'Оператор ДДС',
    group: 'Группа 1',
    active: true,
  },
  {
    login: 'umc_operdds2',
    password: 'dds112-2',
    id: 'u-002',
    name: 'Смирнов Алексей Сергеевич',
    last_name: 'Смирнов',
    role: 'student',
    post: 'Оператор ДДС',
    group: 'Группа 1',
    active: true,
  },
  {
    login: 'umc_teacher',
    password: 'teach112',
    id: 'u-003',
    name: 'Кузнецов Никита Андреевич',
    last_name: 'Кузнецов',
    role: 'teacher',
    post: 'Преподаватель',
    group: null,
    active: true,
  },
  {
    login: 'umc_admin',
    password: 'admin112',
    id: 'u-004',
    name: 'Соколова Дарья Викторовна',
    last_name: 'Соколова',
    role: 'admin',
    post: 'Администратор',
    group: null,
    active: true,
  },
];

const norm = (s) => String(s ?? '').trim().toLowerCase();

export function authenticate(login, password) {
  const acc = ACCOUNTS.find((a) => norm(a.login) === norm(login));
  if (!acc || !acc.active) return { error: 'Пользователь с таким логином не найден' };
  if (acc.password !== String(password ?? '')) return { error: 'Неверный пароль' };
  const { password: _pw, ...user } = acc;
  return { user };
}
