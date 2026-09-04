import { Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/layout/AppShell";
import { DashboardPage } from "./pages/DashboardPage";
import { LibraryPage } from "./pages/LibraryPage";
import { DocumentPage } from "./pages/DocumentPage";
import { ChatPage } from "./pages/ChatPage";
import { StudyPage } from "./pages/StudyPage";
import { SummaryTab } from "./pages/study/SummaryTab";
import { ExplainTab } from "./pages/study/ExplainTab";
import { CompareTab } from "./pages/study/CompareTab";
import { QuizTab } from "./pages/study/QuizTab";
import { MCQTab } from "./pages/study/MCQTab";
import { FlashcardsTab } from "./pages/study/FlashcardsTab";

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/library" element={<LibraryPage />} />
        <Route path="/library/:documentId" element={<DocumentPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/study" element={<StudyPage />}>
          <Route index element={<Navigate to="summary" replace />} />
          <Route path="summary" element={<SummaryTab />} />
          <Route path="explain" element={<ExplainTab />} />
          <Route path="compare" element={<CompareTab />} />
          <Route path="quiz" element={<QuizTab />} />
          <Route path="mcq" element={<MCQTab />} />
          <Route path="flashcards" element={<FlashcardsTab />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppShell>
  );
}
