import { createBrowserRouter, Navigate } from "react-router-dom";
import AppLayout from "../../components/layout/AppLayout";
import ProtectedRoute from "./ProtectedRoute";
import LoginPage from "../../features/auth/LoginPage";
import RegisterPage from "../../features/auth/RegisterPage";
import DashboardPage from "../../features/dashboard/DashboardPage";
import UploadPage from "../../features/exam-analysis/UploadPage";
import ExamAnalysisPage from "../../features/exam-analysis/ExamAnalysisPage";
import RevisionPage from "../../features/revision/RevisionPage";
import SelfAssessmentPage from "../../features/self-assessment/SelfAssessmentPage";
import SkillsPage from "../../features/skills/SkillsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to="/dashboard" replace /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "upload", element: <UploadPage /> },
      { path: "exams/:examId", element: <ExamAnalysisPage /> },
      { path: "revision", element: <RevisionPage /> },
      { path: "self-assessment", element: <SelfAssessmentPage /> },
      { path: "skills", element: <SkillsPage /> },
      { path: "*", element: <Navigate to="/dashboard" replace /> },
    ],
  },
]);
