import { Route, Routes } from 'react-router-dom'
import { MainLayout } from '../layouts/MainLayout'
import { AuthLayout } from '../layouts/AuthLayout'
import { DashboardLayout } from '../layouts/DashboardLayout'
import { ProtectedRoute } from './ProtectedRoute'
import { ROLES } from '../lib/roles'

import { CommunityFeedPage } from '../pages/citizen/CommunityFeedPage'
import { LandingPage } from '../pages/LandingPage'
import { NotFoundPage } from '../pages/NotFoundPage'
import { LoginPage } from '../pages/auth/LoginPage'
import { SignupPage } from '../pages/auth/SignupPage'
import { CitizenDashboard } from '../pages/dashboards/CitizenDashboard'
import { ReportComplaintPage } from '../pages/citizen/ReportComplaintPage'
import { GovernmentDashboard } from '../pages/dashboards/GovernmentDashboard'
import { NGODashboard } from '../pages/dashboards/NGODashboard'
import { AdminDashboard } from '../pages/dashboards/AdminDashboard'

export function AppRoutes() {
  return (
    <Routes>
      {/* Public pages */}
      <Route element={<MainLayout />}>
        <Route path="/" element={<LandingPage />} />
      </Route>

      {/* Auth pages */}
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
      </Route>

      {/* Role-based dashboards — each gated to its own role */}
      <Route element={<DashboardLayout />}>
        <Route
          path="/citizen"
          element={
            <ProtectedRoute allowedRoles={[ROLES.CITIZEN]}>
              <CitizenDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/citizen/report"
          element={
            <ProtectedRoute allowedRoles={[ROLES.CITIZEN]}>
              <ReportComplaintPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/citizen/community"
          element={
            <ProtectedRoute allowedRoles={[ROLES.CITIZEN]}>
              <CommunityFeedPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/government"
          element={
            <ProtectedRoute allowedRoles={[ROLES.GOVERNMENT]}>
              <GovernmentDashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/ngo"
          element={
            <ProtectedRoute allowedRoles={[ROLES.NGO]}>
              <NGODashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <ProtectedRoute allowedRoles={[ROLES.ADMIN]}>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
      </Route>

      {/* Fallback */}
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
