export interface User {
  id: string
  email: string
  name: string
}

export interface Tenant {
  id: string
  name: string
}

export interface TenantUser {
  id: string
  tenant_id: string
  user_id: string
  role: 'admin' | 'manager' | 'member'
  manager_user_id: string | null
  is_active: boolean
}

export interface Project {
  id: string
  tenant_id: string
  name: string
  color: string
  description: string | null
  is_active: boolean
}

export type TaskStatus = 'todo' | 'in_progress' | 'done'

export interface Task {
  id: string
  user_id: string
  project_id: string
  name: string
  estimated_hours: number | null
  status: TaskStatus
  is_private: boolean
  task_date: string
  created_at: string
  updated_at: string
}

export type WeeklyReportStatus = 'draft' | 'ready' | 'submitted' | 'feedback_received'

export interface WeeklyReport {
  id: string
  user_id: string
  tenant_id: string
  week_start_date: string
  ai_summary: string | null
  feeling: string | null
  questions: string | null
  issues: string | null
  status: WeeklyReportStatus
  submitted_at: string | null
  created_at: string
  updated_at: string
}

export type ReactionType = 'like' | 'star' | 'heart' | 'party' | 'muscle' | 'idea'

export interface WeeklyReportFeedback {
  id: string
  weekly_report_id: string
  manager_user_id: string
  comment: string | null
  reactions: ReactionType[]
  created_at: string
}

export interface DashboardTask extends Task {
  user_name: string
  project_name: string
  project_color: string
}

export interface PastIncompleteSummaryItem {
  task_date: string
  count: number
}

export interface PastIncompleteSummary {
  total: number
  items: PastIncompleteSummaryItem[]
}

export interface InboxReport {
  id: string
  user_id: string
  user_name: string
  user_email: string
  week_start_date: string
  ai_summary: string | null
  feeling: string | null
  status: WeeklyReportStatus
  submitted_at: string | null
  feedback?: WeeklyReportFeedback
}
