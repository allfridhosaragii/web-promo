import { describe, expect, it, vi } from "vitest";
import { handleRevalidate } from "./revalidate";

function revalidator() {
  return {
    revalidatePath: vi.fn(),
    revalidateTag: vi.fn(),
  };
}

describe("handleRevalidate (ARCH §17.4)", () => {
  it("secret salah -> 401, tidak ada revalidate", () => {
    const r = revalidator();
    const res = handleRevalidate({
      configuredSecret: "rahasia",
      providedSecret: "salah",
      revalidator: r,
    });
    expect(res.status).toBe(401);
    expect(r.revalidatePath).not.toHaveBeenCalled();
    expect(r.revalidateTag).not.toHaveBeenCalled();
  });

  it("secret belum dikonfigurasi -> 401 (fail closed)", () => {
    const r = revalidator();
    const res = handleRevalidate({
      configuredSecret: undefined,
      providedSecret: "apa-pun",
      revalidator: r,
    });
    expect(res.status).toBe(401);
    expect(r.revalidatePath).not.toHaveBeenCalled();
  });

  it("secret benar -> 200, path + tag direvalidate", () => {
    const r = revalidator();
    const res = handleRevalidate({
      configuredSecret: "rahasia",
      providedSecret: "rahasia",
      paths: ["/", "/promo/abc"],
      tags: ["promos"],
      revalidator: r,
    });
    expect(res.status).toBe(200);
    if (res.status === 200) {
      expect(res.revalidated.paths).toEqual(["/", "/promo/abc"]);
      expect(res.revalidated.tags).toEqual(["promos"]);
    }
    expect(r.revalidatePath).toHaveBeenCalledWith("/");
    expect(r.revalidatePath).toHaveBeenCalledWith("/promo/abc");
    expect(r.revalidateTag).toHaveBeenCalledWith("promos");
  });

  it("path tidak absolut difilter, default path '/' + tag 'promos'", () => {
    const r = revalidator();
    const res = handleRevalidate({
      configuredSecret: "rahasia",
      providedSecret: "rahasia",
      paths: ["https://jahat.test/x", "/promo/abc"],
      revalidator: r,
    });
    expect(res.status).toBe(200);
    if (res.status === 200)
      expect(res.revalidated.paths).toEqual(["/promo/abc"]);
    expect(r.revalidatePath).not.toHaveBeenCalledWith("https://jahat.test/x");
  });
});
