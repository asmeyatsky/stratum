import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import ProjectList from './pages/ProjectList';
import ProjectDetail from './pages/ProjectDetail';
import ComparisonView from './pages/ComparisonView';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="projects" element={<ProjectList />} />
          <Route path="projects/:id/*" element={<ProjectDetail />} />
          <Route path="compare" element={<ComparisonView />} />
          <Route
            path="settings"
            element={
              <div className="flex flex-col items-center justify-center py-32">
                <h2 className="text-xl font-semibold text-navy-300">
                  Settings
                </h2>
                <p className="mt-2 text-sm text-navy-500">
                  Configuration options coming soon.
                </p>
              </div>
            }
          />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
