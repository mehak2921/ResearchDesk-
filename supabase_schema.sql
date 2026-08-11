create table if not exists public.research_history (
    id uuid primary key default gen_random_uuid(),
    topic text not null,
    report text not null,
    created_at timestamptz not null default now()
);

-- Add user_id if upgrading from older version
alter table public.research_history add column if not exists user_id uuid references auth.users(id);

create index if not exists research_history_created_at_idx
    on public.research_history (created_at desc);

create index if not exists research_history_user_id_idx
    on public.research_history (user_id);

alter table public.research_history enable row level security;

-- Drop existing policies to prevent errors if this script is run multiple times
drop policy if exists "Users can view their own history" on public.research_history;
drop policy if exists "Users can insert their own history" on public.research_history;
drop policy if exists "Users can delete their own history" on public.research_history;

-- Allow users to read only their own history
create policy "Users can view their own history"
    on public.research_history
    for select
    to authenticated
    using (auth.uid() = user_id);

-- Allow users to insert their own history
create policy "Users can insert their own history"
    on public.research_history
    for insert
    to authenticated
    with check (auth.uid() = user_id);

-- Allow users to delete their own history
create policy "Users can delete their own history"
    on public.research_history
    for delete
    to authenticated
    using (auth.uid() = user_id);

-- ==========================================
-- CONVERSATIONS TABLE
-- ==========================================
create table if not exists public.conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users(id) not null,
    title text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.conversations enable row level security;

drop policy if exists "Users can view their own conversations" on public.conversations;
create policy "Users can view their own conversations"
    on public.conversations for select
    to authenticated using (auth.uid() = user_id);

drop policy if exists "Users can insert their own conversations" on public.conversations;
create policy "Users can insert their own conversations"
    on public.conversations for insert
    to authenticated with check (auth.uid() = user_id);

drop policy if exists "Users can update their own conversations" on public.conversations;
create policy "Users can update their own conversations"
    on public.conversations for update
    to authenticated using (auth.uid() = user_id);

drop policy if exists "Users can delete their own conversations" on public.conversations;
create policy "Users can delete their own conversations"
    on public.conversations for delete
    to authenticated using (auth.uid() = user_id);



-- ==========================================
-- MESSAGES TABLE
-- ==========================================
create table if not exists public.messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid references public.conversations(id) on delete cascade not null,
    role text not null,
    message_type text not null,
    content text not null,
    created_at timestamptz not null default now()
);

alter table public.messages enable row level security;

drop policy if exists "Users can view messages of their conversations" on public.messages;
create policy "Users can view messages of their conversations"
    on public.messages for select
    to authenticated
    using (
        exists (
            select 1 from public.conversations c 
            where c.id = messages.conversation_id 
            and c.user_id = auth.uid()
        )
    );

drop policy if exists "Users can insert messages to their conversations" on public.messages;
create policy "Users can insert messages to their conversations"
    on public.messages for insert
    to authenticated
    with check (
        exists (
            select 1 from public.conversations c 
            where c.id = conversation_id 
            and c.user_id = auth.uid()
        )
    );

drop policy if exists "Users can delete messages of their conversations" on public.messages;
create policy "Users can delete messages of their conversations"
    on public.messages for delete
    to authenticated
    using (
        exists (
            select 1 from public.conversations c 
            where c.id = messages.conversation_id 
            and c.user_id = auth.uid()
        )
    );

-- ==========================================
-- UPDATE RESEARCH_HISTORY
-- ==========================================
alter table public.research_history add column if not exists conversation_id uuid references public.conversations(id) on delete cascade;

