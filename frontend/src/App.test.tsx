import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, test, vi } from "vitest";
import { App } from "./App";
import { installMockFetch, route } from "./test/mockFetch";

afterEach(() => {
  vi.unstubAllGlobals();
});

test("application starts and shows the dashboard", async () => {
  installMockFetch([route("GET", "/documents", { documents: [] })]);

  render(
    <MemoryRouter initialEntries={["/"]}>
      <App />
    </MemoryRouter>
  );

  expect(await screen.findByText("Welcome back")).toBeInTheDocument();
  expect(screen.getByText("Study Assistant")).toBeInTheDocument();
});
