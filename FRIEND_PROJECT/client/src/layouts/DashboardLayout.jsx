import { Outlet } from 'react-router-dom'
import { Navbar } from '../components/Navbar'

/**
 * Shared chrome for every role dashboard (citizen/government/ngo/admin).
 * Individual dashboards only need to render their own content via <Outlet />;
 * this keeps the navbar and future sidebar/nav in one place.
 */
export function DashboardLayout() {
  return (
    <div className="dashboard-layout">
      <Navbar />
      <div className="dashboard-body">
        <Outlet />
      </div>
    </div>
  )
}
