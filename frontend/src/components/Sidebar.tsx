import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FolderKanban,
  Settings,
  Layers,
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/projects', icon: FolderKanban, label: 'Projects' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Sidebar() {
  return (
    <aside className="flex h-screen w-60 flex-col border-r border-navy-800 bg-navy-950">
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-5 py-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent-blue to-accent-indigo">
          <Layers className="h-4.5 w-4.5 text-white" />
        </div>
        <div>
          <h1 className="text-base font-bold tracking-tight text-white">
            Stratum
          </h1>
          <p className="text-[10px] font-medium uppercase tracking-widest text-navy-500">
            Code Intelligence
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="mt-2 flex-1 space-y-0.5 px-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                isActive
                  ? 'bg-accent-blue/10 text-accent-blue'
                  : 'text-navy-400 hover:bg-navy-800 hover:text-navy-200'
              }`
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Bottom section */}
      <div className="border-t border-navy-800 px-4 py-4">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-navy-800 text-xs font-bold text-navy-400">
            S
          </div>
          <div className="flex-1 min-w-0">
            <p className="truncate text-sm font-medium text-navy-300">
              Stratum
            </p>
            <p className="text-xs text-navy-600">v2.0</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
