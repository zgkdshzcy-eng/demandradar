import { setLocaleAction } from "@/app/actions/locale";
import { type Locale, t } from "@/lib/i18n";

export function LocaleSwitcher({ current }: { current: Locale }) {
  return (
    <div className="flex items-center gap-1 rounded-md border border-slate-800 bg-slate-900/40 p-0.5 text-xs">
      {(["en", "zh"] as const).map((loc) => (
        <form key={loc} action={setLocaleAction}>
          <input type="hidden" name="locale" value={loc} />
          <button
            type="submit"
            className={
              "rounded px-2 py-1 transition " +
              (loc === current
                ? "bg-slate-700 text-white"
                : "text-slate-400 hover:text-white")
            }
            aria-label={loc === "zh" ? t("locale.switch.zh", current) : t("locale.switch.en", current)}
          >
            {loc === "zh" ? "中" : "EN"}
          </button>
        </form>
      ))}
    </div>
  );
}
