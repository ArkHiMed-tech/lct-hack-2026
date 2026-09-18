import { NavLink } from 'react-router-dom';

const MENU = [
  { to: '/', label: 'Главная', icon: '⌂', end: true },
  { to: '/scenarios', label: 'Тренировки', icon: '▦' },
  { to: '/journal', label: 'Журнал', icon: '☰' },
  { to: '/admin', label: 'Администрирование', icon: '⚙', adminOnly: true },
];

export default function SideNav({ role }) {
  const items = MENU.filter((item) => !item.adminOnly || role === 'admin');

  return (
    <nav className="side-nav">
      <ul>
        {items.map((item) => (
          <li key={item.to}>
            <NavLink
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="side-nav-note">Прототип интерфейса</div>
    </nav>
  );
}