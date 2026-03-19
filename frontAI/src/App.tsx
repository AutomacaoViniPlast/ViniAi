import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import Auth from "./pages/Auth";
import { useAuth } from "./hooks/useAuth";

const queryClient = new QueryClient();

// ✅ Componente separado para poder usar hooks dentro do BrowserRouter
const AppRoutes = () => {
  const { user, loading } = useAuth();

  if (loading) return <div className="text-white text-center mt-20">Carregando...</div>;

  if (!user) return <Auth />;

  return (
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
};

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <AppRoutes /> {/* ✅ Hooks usados aqui dentro, onde o BrowserRouter já existe */}
      </BrowserRouter>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;