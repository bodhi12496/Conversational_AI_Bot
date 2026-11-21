import React from "react";
import {
  cleanup,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, expect, test } from "vitest";
import App from "../src/App";
const base = process.env.COE_BASE_URL || "http://127.0.0.1:8017";
const networkFetch = globalThis.fetch;
beforeAll(() => {
  globalThis.fetch = (input, init) =>
    networkFetch(
      typeof input === "string" && input.startsWith("/") ? base + input : input,
      init,
    );
});
afterEach(cleanup);

test("guided UI against real API: create, import, edit, publish, chat, selection, restore", async () => {
  const user = userEvent.setup();
  render(<App />);
  await waitFor(() =>
    expect(screen.queryByText("Working on your request…")).toBeNull(),
  );
  await user.click(
    screen.getByRole("button", { name: "New project", exact: true }),
  );
  await user.type(
    screen.getByLabelText("Project name"),
    "Redesigned interface test",
  );
  await user.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Create project",
      exact: true,
    }),
  );
  await user.click(
    await screen.findByRole("button", { name: "Try sample data" }),
  );
  await screen.findByText(/Sample data loaded/);
  const nav = screen.getByRole("navigation", { name: "Main navigation" });
  await user.click(
    within(nav).getByRole("button", { name: "Chat", exact: true }),
  );
  await screen.findByRole("heading", {
    name: "Publish your assistant to start chatting",
  });
  expect(screen.queryByRole("textbox", { name: "Ask your data" })).toBeNull();
  await user.click(
    within(nav).getByRole("button", { name: "Semantic model", exact: true }),
  );
  for (const instruction of [
    "Define revenue as amount minus refund in sales.",
    "Exclude cancelled orders from sales.",
    "Link sales.product_id to inventory.product_id as many_to_one.",
  ]) {
    await user.click(screen.getByRole("button", { name: "Edit with AI" }));
    await user.type(
      screen.getByLabelText("What would you like to change?"),
      instruction,
    );
    await user.click(screen.getByRole("button", { name: "Preview change" }));
    const save = await screen.findByRole("button", { name: "Save to draft" });
    expect(save.hasAttribute("disabled")).toBe(false);
    await user.click(save);
    await screen.findByText(/Change saved to a new draft/);
  }
  await user.click(screen.getByRole("tab", { name: /Metrics/ }));
  expect(
    screen.getByRole("cell", { name: /revenue.*User-defined/ }),
  ).toBeTruthy();
  await user.click(screen.getByRole("tab", { name: "Relationships" }));
  expect(screen.getByText("many to one")).toBeTruthy();
  await user.click(within(nav).getByRole("button", { name: "Agent setup" }));
  await user.click(
    screen.getByRole("checkbox", { name: /I reviewed the definitions/ }),
  );
  await user.click(screen.getByRole("button", { name: /^Publish v\d+$/ }));
  await screen.findByText(/Assistant published/);
  await user.click(
    within(nav).getByRole("button", { name: "Chat", exact: true }),
  );
  await user.type(
    screen.getByRole("textbox", { name: "Ask your data" }),
    "Show sales.revenue and inventory.total_stock by sales.product_id.",
  );
  await user.click(screen.getByRole("button", { name: "Send", exact: true }));
  const revenue = await screen.findByRole("cell", { name: "290", exact: true });
  expect(
    within(revenue.closest("tr")!).getByRole("cell", {
      name: "12",
      exact: true,
    }),
  ).toBeTruthy();
  expect(screen.getByRole("cell", { name: "P004" })).toBeTruthy();
  await user.click(within(nav).getByRole("button", { name: "Agent setup" }));
  await user.click(screen.getByRole("checkbox", { name: /inventory/i }));
  await user.click(
    screen.getByRole("checkbox", { name: /I reviewed the definitions/ }),
  );
  expect(
    screen.getByRole("button", { name: "Up to date" }).hasAttribute("disabled"),
  ).toBe(true);
  await user.click(
    screen.getByRole("button", { name: "Review selection change" }),
  );
  await user.click(
    await screen.findByRole("button", { name: "Save to draft" }),
  );
  await screen.findByText(/Change saved to a new draft/);
  await user.click(
    within(nav).getByRole("button", { name: "Activity & versions" }),
  );
  await user.selectOptions(screen.getByLabelText("Version to restore"), "3");
  await user.click(screen.getByRole("button", { name: "Restore draft" }));
  await screen.findByText(/Version restored as a new draft/);
  await user.click(screen.getByRole("tab", { name: "Reference tests" }));
  expect(
    screen.getByRole("button", { name: "Add reference test" }),
  ).toBeTruthy();
  await user.click(within(nav).getByRole("button", { name: "Data sources" }));
  await user.type(
    screen.getByRole("textbox", { name: "Search data sources" }),
    "nonexistent",
  );
  expect(screen.getByText("No sources match your search.")).toBeTruthy();
});
