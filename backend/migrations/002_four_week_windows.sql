--
-- 002: 四周窗口画像
-- 按会员/自然周保存阅读指标，窗口版本保存四周画像、缺口清单与发布状态。
-- 重复执行安全（IF NOT EXISTS）；ORM 的 Base.metadata.create_all 亦会创建同一结构。
--

CREATE TABLE IF NOT EXISTS public.weekly_records (
    id integer NOT NULL,
    reader_id integer NOT NULL,
    week character varying(8) NOT NULL,
    reading_count integer NOT NULL,
    completion double precision NOT NULL,
    night_share double precision NOT NULL,
    source character varying(100) NOT NULL DEFAULT 'manual',
    note text DEFAULT '',
    updated_at character varying(40) NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.weekly_records_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.weekly_records_id_seq OWNED BY public.weekly_records.id;
ALTER TABLE ONLY public.weekly_records ALTER COLUMN id SET DEFAULT nextval('public.weekly_records_id_seq');

ALTER TABLE ONLY public.weekly_records
    ADD CONSTRAINT weekly_records_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.weekly_records
    ADD CONSTRAINT uq_weekly_reader_week_source UNIQUE (reader_id, week, source);
CREATE INDEX IF NOT EXISTS ix_weekly_reader_week ON public.weekly_records (reader_id, week);
ALTER TABLE ONLY public.weekly_records
    ADD CONSTRAINT weekly_records_reader_id_fkey FOREIGN KEY (reader_id) REFERENCES public.readers(id);

CREATE TABLE IF NOT EXISTS public.windows (
    id integer NOT NULL,
    anchor_week character varying(8) NOT NULL,
    window_weeks json NOT NULL,
    state character varying(20) NOT NULL DEFAULT 'building',
    result json,
    error text DEFAULT '',
    published_at character varying(40),
    created_at character varying(40) NOT NULL
);

CREATE SEQUENCE IF NOT EXISTS public.windows_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.windows_id_seq OWNED BY public.windows.id;
ALTER TABLE ONLY public.windows ALTER COLUMN id SET DEFAULT nextval('public.windows_id_seq');

ALTER TABLE ONLY public.windows ADD CONSTRAINT windows_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.windows ADD CONSTRAINT uq_windows_anchor UNIQUE (anchor_week);

CREATE TABLE IF NOT EXISTS public.window_profiles (
    id integer NOT NULL,
    window_id integer NOT NULL,
    reader_id integer NOT NULL,
    code character varying(60) NOT NULL,
    status character varying(20) NOT NULL,
    total_reading integer DEFAULT 0,
    weighted_completion double precision,
    weighted_night_share double precision,
    weeks json NOT NULL,
    gap_reason character varying(40)
);

CREATE SEQUENCE IF NOT EXISTS public.window_profiles_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.window_profiles_id_seq OWNED BY public.window_profiles.id;
ALTER TABLE ONLY public.window_profiles ALTER COLUMN id SET DEFAULT nextval('public.window_profiles_id_seq');

ALTER TABLE ONLY public.window_profiles ADD CONSTRAINT window_profiles_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.window_profiles ADD CONSTRAINT uq_window_reader UNIQUE (window_id, reader_id);
CREATE INDEX IF NOT EXISTS ix_window_profile_window ON public.window_profiles (window_id);
ALTER TABLE ONLY public.window_profiles
    ADD CONSTRAINT window_profiles_window_id_fkey FOREIGN KEY (window_id) REFERENCES public.windows(id);

ALTER TABLE ONLY public.segments ADD COLUMN IF NOT EXISTS window_id integer;
ALTER TABLE ONLY public.segments
    ADD CONSTRAINT segments_window_id_fkey FOREIGN KEY (window_id) REFERENCES public.windows(id);
