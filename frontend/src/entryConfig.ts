import type { EntryType } from "./types";

export type FieldKind = "text" | "number" | "score" | "select" | "date";

export interface FieldOption {
  value: string;
  label: string;
}

export interface EntryField {
  name: string;
  label: string;
  kind: FieldKind;
  required?: boolean;
  min?: number;
  max?: number;
  step?: number;
  placeholder?: string;
  options?: FieldOption[];
}

export interface EntryDefinition {
  label: string;
  shortLabel: string;
  icon: string;
  color: string;
  fields: EntryField[];
}

const score = (name: string, label: string, required = false): EntryField => ({
  name,
  label,
  kind: "score",
  required,
  min: 1,
  max: 5,
});

export const entryDefinitions: Record<EntryType, EntryDefinition> = {
  feeding: {
    label: "Кормление",
    shortLabel: "Еда",
    icon: "◒",
    color: "#d6823d",
    fields: [
      { name: "food", label: "Что ел", kind: "text", required: true, placeholder: "Сухой корм" },
      { name: "amount", label: "Количество", kind: "number", min: 0, step: 0.1 },
      {
        name: "unit",
        label: "Единица",
        kind: "select",
        options: [
          { value: "g", label: "г" },
          { value: "kg", label: "кг" },
          { value: "ml", label: "мл" },
          { value: "portion", label: "порция" },
          { value: "piece", label: "штука" },
        ],
      },
      score("appetite", "Аппетит"),
      { name: "reaction", label: "Реакция", kind: "text", placeholder: "Как перенёс еду" },
    ],
  },
  walk: {
    label: "Прогулка",
    shortLabel: "Гуляли",
    icon: "↗",
    color: "#4f8a6c",
    fields: [
      {
        name: "duration_minutes",
        label: "Длительность, минут",
        kind: "number",
        required: true,
        min: 1,
      },
      { name: "distance_km", label: "Расстояние, км", kind: "number", min: 0, step: 0.1 },
      score("energy", "Энергия"),
      score("quality", "Качество прогулки"),
    ],
  },
  symptom: {
    label: "Симптом",
    shortLabel: "Симптом",
    icon: "!",
    color: "#bb574e",
    fields: [
      {
        name: "category",
        label: "Категория",
        kind: "select",
        required: true,
        options: [
          { value: "digestion", label: "Пищеварение" },
          { value: "stool", label: "Стул" },
          { value: "vomiting", label: "Рвота" },
          { value: "reflux", label: "Рефлюкс / срыгивание" },
          { value: "gas", label: "Газы" },
          { value: "pain", label: "Боль" },
          { value: "limping", label: "Хромота" },
          { value: "skin", label: "Кожа" },
          { value: "breathing", label: "Дыхание" },
          { value: "other", label: "Другое" },
        ],
      },
      score("severity", "Тяжесть", true),
      { name: "count", label: "Количество эпизодов", kind: "number", min: 1 },
      { name: "body_area", label: "Область тела", kind: "text" },
      { name: "description", label: "Описание", kind: "text" },
    ],
  },
  wellbeing: {
    label: "Самочувствие",
    shortLabel: "Состояние",
    icon: "●",
    color: "#477a80",
    fields: [
      score("appetite", "Аппетит", true),
      score("energy", "Энергия", true),
      score("mood", "Настроение", true),
      score("sleep", "Сон"),
      score("pain", "Боль"),
    ],
  },
  training: {
    label: "Тренировка",
    shortLabel: "Учились",
    icon: "◆",
    color: "#725b91",
    fields: [
      {
        name: "duration_minutes",
        label: "Длительность, минут",
        kind: "number",
        required: true,
        min: 1,
      },
      {
        name: "commands",
        label: "Команды через запятую",
        kind: "text",
        placeholder: "рядом, место, ко мне",
      },
      score("engagement", "Вовлечённость"),
      { name: "result", label: "Результат", kind: "text" },
    ],
  },
  medication: {
    label: "Лекарство",
    shortLabel: "Лекарство",
    icon: "+",
    color: "#3d77a0",
    fields: [
      { name: "name", label: "Название", kind: "text", required: true },
      { name: "dose", label: "Доза", kind: "number", required: true, min: 0, step: 0.01 },
      {
        name: "unit",
        label: "Единица",
        kind: "select",
        required: true,
        options: [
          { value: "mg", label: "мг" },
          { value: "ml", label: "мл" },
          { value: "tablet", label: "таблетка" },
          { value: "capsule", label: "капсула" },
          { value: "drop", label: "капля" },
          { value: "dose", label: "доза" },
        ],
      },
    ],
  },
  weight: {
    label: "Вес",
    shortLabel: "Вес",
    icon: "≈",
    color: "#72796b",
    fields: [
      {
        name: "weight_kg",
        label: "Вес, кг",
        kind: "number",
        required: true,
        min: 0,
        max: 200,
        step: 0.1,
      },
    ],
  },
  vet_visit: {
    label: "Визит к ветеринару",
    shortLabel: "Ветеринар",
    icon: "✚",
    color: "#386b70",
    fields: [
      { name: "reason", label: "Причина", kind: "text", required: true },
      { name: "diagnosis", label: "Диагноз", kind: "text" },
      { name: "recommendations", label: "Рекомендации", kind: "text" },
      { name: "follow_up_date", label: "Повторный визит", kind: "date" },
    ],
  },
  note: {
    label: "Заметка",
    shortLabel: "Заметка",
    icon: "—",
    color: "#88765f",
    fields: [{ name: "title", label: "Заголовок", kind: "text" }],
  },
};

export const entryOrder: EntryType[] = [
  "feeding",
  "walk",
  "symptom",
  "wellbeing",
  "training",
  "medication",
  "weight",
  "vet_visit",
  "note",
];

