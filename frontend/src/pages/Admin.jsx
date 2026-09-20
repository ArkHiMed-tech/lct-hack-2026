import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import AppHeader from '../components/AppHeader';
import SideNav from '../components/SideNav';
import PageTitle from '../components/PageTitle';

const PLANNED = [
  { title: 'Пользователи', desc: 'CRUD пользователей, назначение ролей и групп (users.json)' },
  { title: 'Сценарии', desc: 'Конструктор сценариев: таймлайн реплик, категории, требуемые службы' },
  { title: 'Рубрики проверки', desc: 'Редактирование чек-листов A–F и критических ошибок (rubrics/*.json)' },
];

export default function Admin() {
  const { user } = useAuth();

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="layout">
        <SideNav role={user.role} />
        <main className="content">
          <div className="dds-back">
            <Link to="/">← Главная</Link>
          </div>
          <PageTitle title="Администрирование" subtitle="Панель доступна роли «Администратор»" />

          <div className="scenario-grid">
            {PLANNED.map((p) => (
              <article key={p.title} className="scenario-card">
                <h3 className="scenario-title">{p.title}</h3>
                <p className="scenario-summary">{p.desc}</p>
                <span className="badge diff-medium">Запланировано</span>
              </article>
            ))}
          </div>
        </main>
      </div>
    </div>
  );
}