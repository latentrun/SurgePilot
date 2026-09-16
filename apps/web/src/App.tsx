import { RouterProvider, createBrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

import { AuthSessionProvider } from "./app/auth-session";
import { routes } from "./app/router";

export function App() {
  const [queryClient] = useState(() => new QueryClient());

  return (
    <QueryClientProvider client={queryClient}>
      <AuthSessionProvider>
        <RouterProvider router={createBrowserRouter(routes)} />
      </AuthSessionProvider>
    </QueryClientProvider>
  );
}
