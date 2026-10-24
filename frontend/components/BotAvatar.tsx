import { Icon } from "./icons";

export default function BotAvatar() {
  return (
    <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-ink text-white ring-2 ring-signal/70 ring-offset-2 ring-offset-mist">
      <Icon name="bot" className="h-5 w-5" />
    </span>
  );
}
