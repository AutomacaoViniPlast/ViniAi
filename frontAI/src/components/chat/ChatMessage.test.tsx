import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import ChatMessage from "./ChatMessage";

describe("ChatMessage", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders markdown tables inside a horizontal scroll wrapper", () => {
    const content = [
      "| # | Produto | Descricao | Total |",
      "|---|---|---|---|",
      "| 1 | TD2AYBR1BOBR100 | SOLLAR TD1000 LD BR/BO/BR 1420MM | 273,91 KG |",
    ].join("\n");

    const { container } = render(
      <ChatMessage id="table-message" role="user" content={content} />
    );

    act(() => {
      vi.runAllTimers();
    });

    const wrapper = container.querySelector(".prose-chat-table-scroll");
    const table = container.querySelector("table");

    expect(wrapper).toBeInTheDocument();
    expect(table).toBeInTheDocument();
    expect(wrapper).toContainElement(table);
  });
});
