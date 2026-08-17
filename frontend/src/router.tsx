import { Navigate, createBrowserRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import MainLayout from './layouts/MainLayout'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import DashboardPage from './pages/DashboardPage'
import ChatPage from './pages/ChatPage'
import ChatHistoryPage from './pages/ChatHistoryPage'
import ChatTranscriptPage from './pages/ChatTranscriptPage'
import KbManagePage from './pages/KbManagePage'
import DoctorWorkbenchPage from './pages/DoctorWorkbenchPage'
import PatientRecordsPage from './pages/PatientRecordsPage'
import AppointmentsPage from './pages/AppointmentsPage'
import HealthInfoPage from './pages/HealthInfoPage'
import VisitGuidePage from './pages/VisitGuidePage'
import PatientManagePage from './pages/PatientManagePage'
import HospitalManagePage from './pages/HospitalManagePage'
import SchedulePage from './pages/SchedulePage'
import NurseWorkbenchPage from './pages/NurseWorkbenchPage'
import AdminManagePage from './pages/AdminManagePage'
import { useAuth } from './stores/auth'
import type { Role } from './types'

function RequireAuth({ children }: { children: ReactNode }) {
  const token = useAuth((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const user = useAuth((s) => s.user)
  if (!user || !roles.includes(user.role)) return <Navigate to="/" replace />
  return <>{children}</>
}

const ALL_ROLES: Role[] = ['patient', 'doctor', 'nurse', 'public', 'admin']

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  {
    path: '/',
    element: (
      <RequireAuth>
        <MainLayout />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: 'chat', element: <ChatPage /> },
      { path: 'chat/history', element: <ChatHistoryPage /> },
      { path: 'chat/history/:id', element: <ChatTranscriptPage /> },
      {
        path: 'kb',
        element: (
          <RequireRole roles={['doctor', 'admin']}>
            <KbManagePage />
          </RequireRole>
        ),
      },
      {
        path: 'patient',
        element: (
          <RequireRole roles={['patient']}>
            <PatientRecordsPage />
          </RequireRole>
        ),
      },
      {
        path: 'appointments',
        element: (
          <RequireRole roles={['patient', 'public']}>
            <AppointmentsPage />
          </RequireRole>
        ),
      },
      { path: 'health', element: <RequireRole roles={ALL_ROLES}><HealthInfoPage /></RequireRole> },
      { path: 'guide', element: <RequireRole roles={ALL_ROLES}><VisitGuidePage /></RequireRole> },
      {
        path: 'doctor',
        element: (
          <RequireRole roles={['doctor']}>
            <DoctorWorkbenchPage />
          </RequireRole>
        ),
      },
      {
        path: 'doctor/patients',
        element: (
          <RequireRole roles={['doctor']}>
            <PatientManagePage />
          </RequireRole>
        ),
      },
      {
        path: 'doctor/hospitalizations',
        element: (
          <RequireRole roles={['doctor']}>
            <HospitalManagePage />
          </RequireRole>
        ),
      },
      {
        path: 'schedule',
        element: (
          <RequireRole roles={['doctor', 'nurse']}>
            <SchedulePage />
          </RequireRole>
        ),
      },
      {
        path: 'nurse',
        element: (
          <RequireRole roles={['nurse']}>
            <NurseWorkbenchPage />
          </RequireRole>
        ),
      },
      {
        path: 'admin',
        element: (
          <RequireRole roles={['admin']}>
            <AdminManagePage />
          </RequireRole>
        ),
      },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
