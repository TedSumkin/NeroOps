import { useCallback, useEffect, useMemo, useState } from "react";
import {
  checkHealth,
  deleteEntry as deleteServerEntry,
  fetchAllEntries,
  fetchBootstrap,
  fetchSummary,
  syncQueue,
  updateEntry,
  updatePet,
} from "./api";
import {
  cacheEntry,
  discardQueueItem,
  enqueue,
  getCachedEntries,
  getMeta,
  removeCachedEntry,
} from "./db";
import { entryDefinitions, entryOrder, type EntryField } from "./entryConfig";
import type { Entry, EntryType, Pet, QueuedFile, Summary, SyncStatus } from "./types";
import {
  dateInput,
  formatDateTime,
  formatDay,
  localDateKey,
  prepareFile,
  toLocalDateTimeInput,
} from "./utils";

type Tab = "today" | "history" | "reports" | "settings";

const labels: Record<string, string> = {
  appetite: "Аппетит",
  energy: "Энергия",
  mood: "Настроение",
  sleep: "Сон",
  pain: "Боль",
  quality: "Качество",
  engagement: "Вовлечённость",
  digestion: "Пищеварение",
  stool: "Стул",
  vomiting: "Рвота",
  reflux: "Рефлюкс",
  gas: "Газы",
  limping: "Хромота",
  skin: "Кожа",
  breathing: "Дыхание",
  other: "Другое",
};

function statusText(status?: SyncStatus): string {
  if (status === "pending") return "Ждёт отправки";
  if (status === "syncing") return "Отправляется";
  if (status === "failed") return "Не отправлено";
  return "Сохранено";
}

function payloadSummary(entry: Entry): string {
  const payload = entry.payload;
  switch (entry.type) {
    case "feeding":
      return [payload.food, payload.amount && `${payload.amount} ${payload.unit ?? ""}`]
        .filter(Boolean)
        .join(" · ");
    case "walk":
      return `${payload.duration_minutes} мин${payload.distance_km ? ` · ${payload.distance_km} км` : ""}`;
    case "symptom":
      return `${labels[String(payload.category)] ?? payload.category} · тяжесть ${payload.severity}/5`;
    case "wellbeing":
      return `энергия ${payload.energy}/5 · настроение ${payload.mood}/5`;
    case "training":
      return `${payload.duration_minutes} мин${Array.isArray(payload.commands) && payload.commands.length ? ` · ${payload.commands.join(", ")}` : ""}`;
    case "medication":
      return `${payload.name} · ${payload.dose} ${payload.unit}`;
    case "weight":
      return `${payload.weight_kg} кг`;
    case "vet_visit":
      return String(payload.reason);
    case "note":
      return String(payload.title || entry.note || "Без заголовка");
  }
}

function localSummary(entries: Entry[], from: string, to: string): Summary {
  const filtered = entries.filter((entry) => {
    const day = localDateKey(entry.occurred_at);
    return day >= from && day <= to;
  });
  const counts: Record<string, number> = {};
  const symptoms: Record<string, number> = {};
  const scoreValues: Record<string, number[]> = {};
  const daily: Record<string, number> = {};
  const weight: Summary["weight_series"] = [];
  for (const entry of filtered) {
    counts[entry.type] = (counts[entry.type] ?? 0) + 1;
    const day = localDateKey(entry.occurred_at);
    daily[day] = (daily[day] ?? 0) + 1;
    if (entry.type === "symptom") {
      const category = String(entry.payload.category);
      symptoms[category] = (symptoms[category] ?? 0) + Number(entry.payload.count ?? 1);
    }
    if (entry.type === "weight") {
      weight.push({
        occurred_at: entry.occurred_at,
        weight_kg: Number(entry.payload.weight_kg),
      });
    }
    for (const key of ["appetite", "energy", "mood", "sleep", "pain", "quality", "engagement"]) {
      const value = entry.payload[key];
      if (typeof value === "number") (scoreValues[key] ??= []).push(value);
    }
  }
  const averages = Object.fromEntries(
    Object.entries(scoreValues).map(([key, values]) => [
      key,
      Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100) / 100,
    ]),
  );
  return {
    from_date: from,
    to_date: to,
    total_entries: filtered.length,
    counts_by_type: counts,
    symptom_counts: symptoms,
    average_scores: averages,
    weight_series: weight.sort((a, b) => a.occurred_at.localeCompare(b.occurred_at)),
    daily_counts: Object.entries(daily)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, count]) => ({ date, count })),
  };
}

function Header({
  pet,
  pendingCount,
  online,
  onSync,
}: {
  pet?: Pet;
  pendingCount: number;
  online: boolean;
  onSync: () => void;
}) {
  return (
    <header className="app-header">
      <div>
        <p className="eyebrow">NEROOPS</p>
        <h1>{pet?.name ?? "Неро"}</h1>
      </div>
      <button className="connection-pill" onClick={onSync} type="button">
        <span className={`connection-dot ${online ? "online" : "offline"}`} />
        {pendingCount > 0 ? `${pendingCount} в очереди` : online ? "На связи" : "Офлайн"}
      </button>
    </header>
  );
}

function QuickActions({ onSelect }: { onSelect: (type: EntryType) => void }) {
  return (
    <section>
      <div className="section-heading">
        <h2>Записать</h2>
        <span>одно касание</span>
      </div>
      <div className="quick-grid">
        {entryOrder.slice(0, 6).map((type) => {
          const definition = entryDefinitions[type];
          return (
            <button
              className="quick-action"
              key={type}
              onClick={() => onSelect(type)}
              style={{ "--accent": definition.color } as React.CSSProperties}
              type="button"
            >
              <span className="quick-icon">{definition.icon}</span>
              <span>{definition.shortLabel}</span>
            </button>
          );
        })}
      </div>
      <button className="all-actions" onClick={() => onSelect("note")} type="button">
        Все типы записей
        <span>→</span>
      </button>
    </section>
  );
}

function EntryCard({
  entry,
  onDelete,
  onEdit,
}: {
  entry: Entry;
  onDelete?: (entry: Entry) => void;
  onEdit?: (entry: Entry) => void;
}) {
  const definition = entryDefinitions[entry.type];
  return (
    <article className="entry-card">
      <div className="entry-mark" style={{ background: definition.color }}>
        {definition.icon}
      </div>
      <div className="entry-body">
        <div className="entry-title-row">
          <strong>{definition.label}</strong>
          <time>{formatDateTime(entry.occurred_at)}</time>
        </div>
        <p className="entry-summary">{payloadSummary(entry)}</p>
        {entry.note && entry.type !== "note" && <p className="entry-note">{entry.note}</p>}
        {entry.attachments.length > 0 && (
          <div className="attachment-strip">
            {entry.attachments.map((attachment) =>
              attachment.mime_type.startsWith("image/") ? (
                <a href={attachment.url} key={attachment.id} target="_blank" rel="noreferrer">
                  <img alt={attachment.filename} src={attachment.url} />
                </a>
              ) : (
                <a className="file-chip" href={attachment.url} key={attachment.id}>
                  PDF
                </a>
              ),
            )}
          </div>
        )}
        <div className="entry-footer">
          <span className={`sync-label ${entry.sync_status ?? "synced"}`}>
            {statusText(entry.sync_status)}
          </span>
          {(onEdit || onDelete) && (
            <span className="entry-actions">
              {onEdit && entry.sync_status === "synced" && (
                <button onClick={() => onEdit(entry)} type="button">
                  Изменить
                </button>
              )}
              {onDelete && (
                <button className="danger-link" onClick={() => onDelete(entry)} type="button">
                  Удалить
                </button>
              )}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}

function EntryFieldControl({
  field,
  value,
  onChange,
}: {
  field: EntryField;
  value: string;
  onChange: (value: string) => void;
}) {
  if (field.kind === "score") {
    return (
      <fieldset className="score-field">
        <legend>{field.label}</legend>
        <div className="score-options">
          {[1, 2, 3, 4, 5].map((scoreValue) => (
            <button
              className={value === String(scoreValue) ? "selected" : ""}
              key={scoreValue}
              onClick={() => onChange(String(scoreValue))}
              type="button"
            >
              {scoreValue}
            </button>
          ))}
        </div>
      </fieldset>
    );
  }
  return (
    <label className="form-field">
      <span>{field.label}</span>
      {field.kind === "select" ? (
        <select required={field.required} value={value} onChange={(event) => onChange(event.target.value)}>
          <option value="">Не выбрано</option>
          {field.options?.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          max={field.max}
          min={field.min}
          placeholder={field.placeholder}
          required={field.required}
          step={field.step}
          type={field.kind}
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      )}
    </label>
  );
}

function EntryForm({
  pet,
  initialType,
  editing,
  onClose,
  onSaved,
}: {
  pet: Pet;
  initialType: EntryType;
  editing?: Entry;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [type, setType] = useState<EntryType>(editing?.type ?? initialType);
  const [occurredAt, setOccurredAt] = useState(
    editing ? toLocalDateTimeInput(new Date(editing.occurred_at)) : toLocalDateTimeInput(),
  );
  const [note, setNote] = useState(editing?.note ?? "");
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      Object.entries(editing?.payload ?? {}).map(([key, value]) => [
        key,
        Array.isArray(value) ? value.join(", ") : String(value),
      ]),
    ),
  );
  const [files, setFiles] = useState<File[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const definition = entryDefinitions[type];

  const changeType = (nextType: EntryType) => {
    if (editing) return;
    setType(nextType);
    setValues({});
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, unknown> = {};
      for (const field of definition.fields) {
        const value = values[field.name];
        if (!value) continue;
        if (field.name === "commands") {
          payload[field.name] = value.split(",").map((item) => item.trim()).filter(Boolean);
        } else if (field.kind === "number" || field.kind === "score") {
          payload[field.name] = Number(value);
        } else {
          payload[field.name] = value;
        }
      }

      if (editing) {
        if (!navigator.onLine) throw new Error("Редактирование сохранённой записи требует сети");
        const updated = await updateEntry(editing.id, {
          occurred_at: new Date(occurredAt).toISOString(),
          note: note || null,
          payload,
        });
        await cacheEntry({ ...updated, sync_status: "synced" });
      } else {
        const entry: Entry = {
          id: crypto.randomUUID(),
          pet_id: pet.id,
          type,
          occurred_at: new Date(occurredAt).toISOString(),
          note: note || null,
          payload,
          attachments: [],
          sync_status: "pending",
        };
        const preparedFiles: QueuedFile[] = [];
        for (const file of files.slice(0, 5)) {
          const prepared = await prepareFile(file);
          preparedFiles.push({ id: crypto.randomUUID(), ...prepared });
        }
        await enqueue({
          id: entry.id,
          entry,
          files: preparedFiles,
          status: "pending",
        });
      }
      onSaved();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Не удалось сохранить запись");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="entry-sheet" role="dialog" aria-modal="true">
        <div className="sheet-handle" />
        <div className="sheet-header">
          <div>
            <p className="eyebrow">{editing ? "РЕДАКТИРОВАНИЕ" : "НОВАЯ ЗАПИСЬ"}</p>
            <h2>{definition.label}</h2>
          </div>
          <button className="close-button" onClick={onClose} type="button" aria-label="Закрыть">
            ×
          </button>
        </div>
        {!editing && (
          <div className="type-scroller">
            {entryOrder.map((entryType) => (
              <button
                className={type === entryType ? "active" : ""}
                key={entryType}
                onClick={() => changeType(entryType)}
                type="button"
              >
                {entryDefinitions[entryType].shortLabel}
              </button>
            ))}
          </div>
        )}
        <form onSubmit={submit}>
          <label className="form-field">
            <span>Когда</span>
            <input
              required
              type="datetime-local"
              value={occurredAt}
              onChange={(event) => setOccurredAt(event.target.value)}
            />
          </label>
          <div className="dynamic-fields">
            {definition.fields.map((field) => (
              <EntryFieldControl
                field={field}
                key={field.name}
                value={values[field.name] ?? (field.name === "count" ? "1" : "")}
                onChange={(value) => setValues((current) => ({ ...current, [field.name]: value }))}
              />
            ))}
          </div>
          <label className="form-field">
            <span>Заметка</span>
            <textarea
              placeholder="Что ещё важно запомнить?"
              rows={3}
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          {!editing && (
            <label className="file-picker">
              <input
                accept="image/*,application/pdf"
                multiple
                type="file"
                onChange={(event) => setFiles(Array.from(event.target.files ?? []).slice(0, 5))}
              />
              <span>＋ Фото или PDF</span>
              <small>{files.length ? `Выбрано: ${files.length}` : "до 5 файлов"}</small>
            </label>
          )}
          {error && <p className="form-error">{error}</p>}
          <button className="primary-button" disabled={saving} type="submit">
            {saving ? "Сохраняю…" : editing ? "Сохранить изменения" : "Записать"}
          </button>
        </form>
      </section>
    </div>
  );
}

function TodayView({
  entries,
  onAdd,
}: {
  entries: Entry[];
  onAdd: (type: EntryType) => void;
}) {
  const today = new Date().toDateString();
  const todayEntries = entries.filter(
    (entry) => new Date(entry.occurred_at).toDateString() === today,
  );
  const latestWeight = entries.find((entry) => entry.type === "weight");
  const symptomsToday = todayEntries.filter((entry) => entry.type === "symptom").length;
  const walkMinutes = todayEntries
    .filter((entry) => entry.type === "walk")
    .reduce((sum, entry) => sum + Number(entry.payload.duration_minutes ?? 0), 0);

  return (
    <main>
      <section className="hero-card">
        <div>
          <p className="eyebrow">СЕГОДНЯ</p>
          <h2>{todayEntries.length ? "День записывается" : "Как Неро сегодня?"}</h2>
          <p>
            {todayEntries.length
              ? `${todayEntries.length} событий уже сохранено`
              : "Добавь первое наблюдение, даже самое короткое."}
          </p>
        </div>
        <div className="hero-orbit">N</div>
      </section>

      <QuickActions onSelect={onAdd} />

      <section>
        <div className="section-heading">
          <h2>Сводка дня</h2>
          <span>{new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(new Date())}</span>
        </div>
        <div className="metric-grid">
          <div className="metric-card">
            <strong>{walkMinutes}</strong>
            <span>минут прогулок</span>
          </div>
          <div className="metric-card">
            <strong>{symptomsToday}</strong>
            <span>симптомов</span>
          </div>
          <div className="metric-card wide">
            <strong>{latestWeight ? `${latestWeight.payload.weight_kg} кг` : "—"}</strong>
            <span>последний вес</span>
          </div>
        </div>
      </section>

      <section>
        <div className="section-heading">
          <h2>Последнее</h2>
          <span>{todayEntries.length}</span>
        </div>
        <div className="entry-list">
          {todayEntries.slice(0, 5).map((entry) => (
            <EntryCard entry={entry} key={entry.id} />
          ))}
          {!todayEntries.length && <EmptyState text="Сегодня пока нет записей" />}
        </div>
      </section>
    </main>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="empty-state">
      <span>○</span>
      <p>{text}</p>
    </div>
  );
}

function HistoryView({
  entries,
  onDelete,
  onEdit,
}: {
  entries: Entry[];
  onDelete: (entry: Entry) => void;
  onEdit: (entry: Entry) => void;
}) {
  const [filter, setFilter] = useState<EntryType | "all">("all");
  const filtered = filter === "all" ? entries : entries.filter((entry) => entry.type === filter);
  const groups = filtered.reduce<Record<string, Entry[]>>((result, entry) => {
    const key = localDateKey(entry.occurred_at);
    (result[key] ??= []).push(entry);
    return result;
  }, {});

  return (
    <main>
      <div className="page-title">
        <p className="eyebrow">ХРОНОЛОГИЯ</p>
        <h2>История</h2>
      </div>
      <div className="type-scroller history-filter">
        <button className={filter === "all" ? "active" : ""} onClick={() => setFilter("all")}>
          Все
        </button>
        {entryOrder.map((type) => (
          <button
            className={filter === type ? "active" : ""}
            key={type}
            onClick={() => setFilter(type)}
          >
            {entryDefinitions[type].shortLabel}
          </button>
        ))}
      </div>
      {Object.entries(groups).map(([day, dayEntries]) => (
        <section className="history-day" key={day}>
          <h3>{formatDay(`${day}T12:00:00`)}</h3>
          <div className="entry-list">
            {dayEntries.map((entry) => (
              <EntryCard entry={entry} key={entry.id} onDelete={onDelete} onEdit={onEdit} />
            ))}
          </div>
        </section>
      ))}
      {!filtered.length && <EmptyState text="Подходящих записей нет" />}
    </main>
  );
}

function ReportView({ entries }: { entries: Entry[] }) {
  const today = new Date();
  const monthAgo = new Date(today);
  monthAgo.setDate(today.getDate() - 30);
  const [from, setFrom] = useState(dateInput(monthAgo));
  const [to, setTo] = useState(dateInput(today));
  const [summary, setSummary] = useState<Summary>(() => localSummary(entries, from, to));
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setSummary(localSummary(entries, from, to));
    if (navigator.onLine) {
      setLoading(true);
      fetchSummary(from, to)
        .then(setSummary)
        .catch(() => undefined)
        .finally(() => setLoading(false));
    }
  }, [entries, from, to]);

  const maxDaily = Math.max(1, ...summary.daily_counts.map((item) => item.count));
  return (
    <main>
      <div className="page-title">
        <p className="eyebrow">НАБЛЮДЕНИЯ</p>
        <h2>Отчёты</h2>
      </div>
      <div className="date-range">
        <label>
          <span>С</span>
          <input type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
        </label>
        <label>
          <span>По</span>
          <input type="date" value={to} onChange={(event) => setTo(event.target.value)} />
        </label>
      </div>
      {loading && <p className="subtle-status">Обновляю с сервера…</p>}
      <section className="report-lead">
        <strong>{summary.total_entries}</strong>
        <span>наблюдений за период</span>
      </section>
      <section>
        <div className="section-heading">
          <h2>Активность</h2>
          <span>по дням</span>
        </div>
        <div className="bar-chart">
          {summary.daily_counts.length ? (
            summary.daily_counts.map((item) => (
              <div className="bar-column" key={item.date}>
                <div
                  className="bar"
                  style={{ height: `${Math.max(8, (item.count / maxDaily) * 100)}%` }}
                  title={`${item.date}: ${item.count}`}
                />
                <span>{new Date(`${item.date}T12:00:00`).getDate()}</span>
              </div>
            ))
          ) : (
            <EmptyState text="Нет данных за этот период" />
          )}
        </div>
      </section>
      <section>
        <div className="section-heading">
          <h2>По типам</h2>
        </div>
        <div className="report-list">
          {Object.entries(summary.counts_by_type)
            .sort(([, left], [, right]) => right - left)
            .map(([type, count]) => (
              <div key={type}>
                <span>{entryDefinitions[type as EntryType]?.label ?? type}</span>
                <strong>{count}</strong>
              </div>
            ))}
        </div>
      </section>
      <section>
        <div className="section-heading">
          <h2>Средние оценки</h2>
          <span>из 5</span>
        </div>
        <div className="score-report">
          {Object.entries(summary.average_scores).map(([key, value]) => (
            <div key={key}>
              <span>{labels[key] ?? key}</span>
              <div>
                <i style={{ width: `${(value / 5) * 100}%` }} />
              </div>
              <strong>{value}</strong>
            </div>
          ))}
          {!Object.keys(summary.average_scores).length && <EmptyState text="Пока нет оценок" />}
        </div>
      </section>
      {summary.weight_series.length > 0 && (
        <section>
          <div className="section-heading">
            <h2>Вес</h2>
            <span>последние измерения</span>
          </div>
          <div className="weight-list">
            {summary.weight_series.slice(-6).reverse().map((item) => (
              <div key={item.occurred_at}>
                <span>{formatDateTime(item.occurred_at)}</span>
                <strong>{item.weight_kg} кг</strong>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

function SettingsView({ pet, onPetUpdated }: { pet: Pet; onPetUpdated: (pet: Pet) => void }) {
  const [form, setForm] = useState(pet);
  const [status, setStatus] = useState("");
  const savePet = async (event: React.FormEvent) => {
    event.preventDefault();
    setStatus("Сохраняю…");
    try {
      const updated = await updatePet({
        name: form.name,
        species: form.species,
        breed: form.breed,
        birth_date: form.birth_date,
      });
      onPetUpdated(updated);
      setStatus("Сохранено");
    } catch {
      setStatus("Нужна связь с сервером");
    }
  };
  return (
    <main>
      <div className="page-title">
        <p className="eyebrow">СИСТЕМА</p>
        <h2>Настройки</h2>
      </div>
      <section className="settings-card">
        <h3>Профиль Неро</h3>
        <form onSubmit={savePet}>
          <label className="form-field">
            <span>Имя</span>
            <input
              required
              value={form.name}
              onChange={(event) => setForm({ ...form, name: event.target.value })}
            />
          </label>
          <label className="form-field">
            <span>Порода</span>
            <input
              value={form.breed ?? ""}
              onChange={(event) => setForm({ ...form, breed: event.target.value || null })}
            />
          </label>
          <label className="form-field">
            <span>Дата рождения</span>
            <input
              type="date"
              value={form.birth_date ?? ""}
              onChange={(event) => setForm({ ...form, birth_date: event.target.value || null })}
            />
          </label>
          <button className="secondary-button" type="submit">
            Сохранить профиль
          </button>
          {status && <p className="subtle-status">{status}</p>}
        </form>
      </section>
      <section className="settings-card">
        <h3>Данные</h3>
        <p>Полный архив содержит JSON, CSV и все прикреплённые файлы.</p>
        <a className="secondary-button download-link" href="/api/v1/export">
          Скачать экспорт
        </a>
      </section>
      <section className="settings-card">
        <h3>О приложении</h3>
        <p>
          NeroOps хранит наблюдения и помогает замечать изменения. Он не ставит диагнозы и не
          заменяет ветеринара.
        </p>
        <span className="version">Версия 0.1.0</span>
      </section>
    </main>
  );
}

function Navigation({ active, onChange }: { active: Tab; onChange: (tab: Tab) => void }) {
  const items: Array<{ tab: Tab; label: string; icon: string }> = [
    { tab: "today", label: "Сегодня", icon: "⌂" },
    { tab: "history", label: "История", icon: "≡" },
    { tab: "reports", label: "Отчёты", icon: "⌁" },
    { tab: "settings", label: "Ещё", icon: "•••" },
  ];
  return (
    <nav className="bottom-nav">
      {items.map((item) => (
        <button
          className={active === item.tab ? "active" : ""}
          key={item.tab}
          onClick={() => onChange(item.tab)}
          type="button"
        >
          <span>{item.icon}</span>
          {item.label}
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  const [tab, setTab] = useState<Tab>("today");
  const [pet, setPet] = useState<Pet>();
  const [entries, setEntries] = useState<Entry[]>([]);
  const [formType, setFormType] = useState<EntryType>();
  const [editing, setEditing] = useState<Entry>();
  const [online, setOnline] = useState(navigator.onLine);
  const [syncTick, setSyncTick] = useState(0);
  const pendingCount = useMemo(
    () => entries.filter((entry) => entry.sync_status && entry.sync_status !== "synced").length,
    [entries],
  );

  const loadLocal = useCallback(async () => {
    const [cachedEntries, cachedPet] = await Promise.all([
      getCachedEntries(),
      getMeta<Pet>("pet"),
    ]);
    setEntries(cachedEntries);
    if (cachedPet) setPet(cachedPet);
  }, []);

  const synchronize = useCallback(async () => {
    if (!navigator.onLine) {
      setOnline(false);
      await loadLocal();
      return;
    }
    try {
      await syncQueue(() => setSyncTick((value) => value + 1));
      const bootstrap = await fetchBootstrap();
      await fetchAllEntries();
      setPet(bootstrap.pet);
      setOnline(true);
    } catch (error) {
      setOnline(false);
      throw error;
    } finally {
      await loadLocal();
    }
  }, [loadLocal]);

  useEffect(() => {
    loadLocal().then(synchronize).catch(() => loadLocal());
  }, [loadLocal, synchronize]);

  useEffect(() => {
    const connected = () => {
      setOnline(true);
      synchronize();
    };
    const disconnected = () => setOnline(false);
    window.addEventListener("online", connected);
    window.addEventListener("offline", disconnected);
    return () => {
      window.removeEventListener("online", connected);
      window.removeEventListener("offline", disconnected);
    };
  }, [synchronize]);

  useEffect(() => {
    loadLocal();
  }, [syncTick, loadLocal]);

  useEffect(() => {
    const updateConnection = async () => {
      setOnline(navigator.onLine && (await checkHealth()));
    };
    const timer = window.setInterval(updateConnection, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const closeForm = () => {
    setFormType(undefined);
    setEditing(undefined);
  };

  const saved = async () => {
    closeForm();
    await loadLocal();
    await synchronize();
  };

  const removeEntry = async (entry: Entry) => {
    if (!window.confirm("Удалить эту запись?")) return;
    if (entry.sync_status && entry.sync_status !== "synced") {
      await discardQueueItem(entry.id);
    } else {
      if (!navigator.onLine) {
        window.alert("Для удаления сохранённой записи нужна связь с сервером.");
        return;
      }
      await deleteServerEntry(entry.id);
      await removeCachedEntry(entry.id);
    }
    await loadLocal();
  };

  if (!pet) {
    return (
      <div className="boot-screen">
        <span className="boot-logo">N</span>
        <p>Загружаю NeroOps…</p>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <Header pet={pet} pendingCount={pendingCount} online={online} onSync={synchronize} />
      {tab === "today" && <TodayView entries={entries} onAdd={setFormType} />}
      {tab === "history" && (
        <HistoryView
          entries={entries}
          onDelete={removeEntry}
          onEdit={(entry) => {
            setEditing(entry);
            setFormType(entry.type);
          }}
        />
      )}
      {tab === "reports" && <ReportView entries={entries} />}
      {tab === "settings" && <SettingsView pet={pet} onPetUpdated={setPet} />}
      <button className="floating-add" onClick={() => setFormType("note")} type="button" aria-label="Добавить">
        +
      </button>
      <Navigation active={tab} onChange={setTab} />
      {formType && (
        <EntryForm
          editing={editing}
          initialType={formType}
          pet={pet}
          onClose={closeForm}
          onSaved={saved}
        />
      )}
    </div>
  );
}
