CREATE EXTENSION IF NOT EXISTS pgcrypto; -- pro gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext; -- case-insensitive text


-- // metadata / reference_id / notes
-- // Add indexes on tag_id, account_id, and time like columns. Consider partitioning transactions by time if volume is very high.
-- // Consider row-level security/audit logging if needed.

-- make sure all the trigger constraints work (in tests?)

-- make soft deletes cascade on other deletes/soft deletes?

-- add logs tables (maybe not tables, outside db)

-- allow negative balances here, but forbid them in the backend code

-- add wallet expiration after some time if there is no owner

-- ======================== employees ========================
CREATE TABLE IF NOT EXISTS employees (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username        text NOT NULL,
  email           citext NOT NULL, -- add verification
  password_hash   text NOT NULL, -- Argon2 hash string (contains salt)
  is_admin        boolean NOT NULL DEFAULT FALSE,
  created_by      uuid REFERENCES employees(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz -- NULL -> existuje, NOT NULL -> smazáno
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_employees_username_active ON employees (LOWER(username)) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_employees_email_active ON employees (email) WHERE deleted_at IS NULL;

-- blokuje delete a změnu created_at, created_by a znovu nastavení deleted_at, když není null:
-- u insert/update odstraní mezery na začátku a konci pro email/username
CREATE OR REPLACE FUNCTION employees_block_delete_limit_update_insert()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    IF (NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
      RAISE EXCEPTION 'created_by is immutable and cannot be changed';
    END IF;
    IF (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at) THEN
      RAISE EXCEPTION 'can not change deleted_at after deletion';
    END IF;
  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE employees
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    NEW.username := trim(NEW.username);
    NEW.email := trim(NEW.email);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_employees_block_delete_limit_update_insert
  BEFORE UPDATE OR DELETE OR INSERT ON employees
  FOR EACH ROW
  EXECUTE FUNCTION employees_block_delete_limit_update_insert();



-- ======================== users ========================
CREATE TABLE IF NOT EXISTS users (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  username        text NOT NULL,
  email           citext NOT NULL, -- add verification
  password_hash   text NOT NULL, -- Argon2 hash string (contains salt)
  created_at      timestamptz NOT NULL DEFAULT now(),
  deleted_at      timestamptz -- NULL -> existuje, NOT NULL -> smazáno
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_users_username_active ON users (LOWER(username)) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_users_email_active ON users (email) WHERE deleted_at IS NULL;

-- blokuje delete a změnu created_at a znovu nastavení deleted_at, když není null:
-- u insert/update odstraní mezery na začátku a konci pro email/username
CREATE OR REPLACE FUNCTION users_block_delete_limit_update_insert()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    IF (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at) THEN
      RAISE EXCEPTION 'can not change deleted_at after deletion';
    END IF;
  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE users
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    NEW.username := trim(NEW.username);
    NEW.email := trim(NEW.email);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_users_block_delete_limit_update_insert
  BEFORE UPDATE OR DELETE OR INSERT ON users
  FOR EACH ROW
  EXECUTE FUNCTION users_block_delete_limit_update_insert();



-- ======================== products ========================
-- transakce se sem neodkazují, protože se řádky mohou jakkoliv měnit
-- potřebné hodnoty se pouze zkopírují
CREATE TABLE IF NOT EXISTS products (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text NOT NULL,
  description   text
);



-- ======================== product_images ========================
-- User uploads via HTML form or AJAX.
-- Validate file (MIME type, magic bytes, max size (max: 5-10MB?)).
-- Sanitize filename, generate unique name (UUID), and save to storage.
-- Optionally create resized versions / thumbnails and save those too.
-- Store metadata + path/URL in DB.
-- Serve images via CDN or static server. Use cache headers. 

-- Use werkzeug.utils.secure_filename() plus prefix with UUID (avoid collisions and path traversal).
-- Strip/normalize EXIF if you care about privacy/location.
-- Set proper permissions on saved files (read by web server only).
-- Prevent users from uploading HTML or scripts disguised as images.
-- Rate-limit uploads and virus-scan if necessary.

-- Serve static images directly with Nginx (or CDN). For authenticated resources, use signed URLs or X-Accel-Redirect / X-Sendfile so app doesn't stream the file.
-- Use Cache-Control headers and long TTLs for immutable files (change filename on update).
-- Create multiple sizes and use srcset in HTML for responsive images. Example:

-- <img alt="..." src="/static/uploads/products/uid_thumb.jpg"
--      srcset="/static/uploads/products/uid_small.jpg 300w,
--              /static/uploads/products/uid_medium.jpg 800w,
--              /static/uploads/products/uid_large.jpg 1200w"
--      sizes="(max-width:600px) 300px, (max-width:1200px) 800px, 1200px" loading="lazy">
CREATE TABLE IF NOT EXISTS product_images (
  id            int GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY,
  product_id    uuid REFERENCES products(id) ON DELETE CASCADE,
  image_path    text NOT NULL,
  filename      text NOT NULL,
  content_type  text NOT NULL CHECK (content_type IN ('image/jpeg', 'image/png', 'image/webp')), --Validate by reading file header/magic bytes, not only extension
  size_bytes    int NOT NULL,
  width         int NOT NULL,
  height        int NOT NULL,
  alt_text      text NOT NULL,
  uploaded_at   timestamptz NOT NULL DEFAULT now()
);



-- ======================== events ========================
CREATE TABLE IF NOT EXISTS events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  start_at    timestamptz,
  end_at      timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  created_by  uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
  deleted_at timestamptz,
  CHECK (start_at < end_at)
  -- deletion? (through deleted_at or actually delete it and all (or some) related stuff but make sure there is a big warning or no deletion allowed)
  -- or only allow deletion for events with nothing import referencing it or stuff that references it
);

-- blokuje delete a změnu created_at, created_by
-- zajistí že end_at jde pouze nastavit po now()
CREATE OR REPLACE FUNCTION events_block_delete_limit_update_insert()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    IF (NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
      RAISE EXCEPTION 'created_by is immutable and cannot be changed';
    END IF;

  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE events
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;

  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    IF NEW.end_at <= now() THEN
      RAISE EXCEPTION 'end_at can not be set to before now()';
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_events_block_delete_limit_update_insert
  BEFORE UPDATE OR DELETE OR INSERT ON events
  FOR EACH ROW
  EXECUTE FUNCTION events_block_delete_limit_update_insert();



-- ======================== booths ========================
CREATE TABLE IF NOT EXISTS booths (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name            text NOT NULL,
  event_id        uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
  booth_type      text NOT NULL CHECK (booth_type IN ('cashier', 'seller')),
  auth_required   boolean NOT NULL DEFAULT TRUE, -- TRUE -> event_manager nebo admin musí na počítaci povolit
  created_at      timestamptz NOT NULL DEFAULT now(),
  created_by      uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
  deleted_at      timestamptz
);

-- blokuje delete a změnu event_id, booth_type, created_at, created_by a znovu nastavení deleted_at, když není null:
CREATE OR REPLACE FUNCTION booths_block_delete_limit_update()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    IF (NEW.created_by IS DISTINCT FROM OLD.created_by) THEN
      RAISE EXCEPTION 'created_by is immutable and cannot be changed';
    END IF;
    IF (NEW.event_id IS DISTINCT FROM OLD.event_id) THEN
      RAISE EXCEPTION 'event_id is immutable and cannot be changed';
    END IF;
    IF (NEW.booth_type IS DISTINCT FROM OLD.booth_type) THEN
      RAISE EXCEPTION 'booth_type is immutable and cannot be changed';
    END IF;
    IF (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at) THEN
      RAISE EXCEPTION 'can not change deleted_at after deletion';
    END IF;

  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE booths
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_booths_block_delete_limit_update
  BEFORE UPDATE OR DELETE ON booths
  FOR EACH ROW
  EXECUTE FUNCTION booths_block_delete_limit_update();



-- ======================== employee_event_booth_roles ========================
-- seller: může dělat payments
-- cashier: může dělat withdrawals and deposits
-- event_manager: může dělat cokoliv v akci (např dávat účtům roli cashier)
-- admin: (není částí této tabulky) může věci mimo akce (např. vytvářet účty)
CREATE TABLE IF NOT EXISTS employee_event_booth_roles (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  employee_id   uuid REFERENCES employees(id) NOT NULL,
  event_id      uuid REFERENCES events(id) NOT NULL,
  booth_id      uuid REFERENCES booths(id), -- null -> event_manager
  role          text NOT NULL CHECK (role IN ('event_manager','cashier','seller')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (employee_id, event_id, booth_id)
);
-- v této tabulce jsou delete i update povoleny
CREATE UNIQUE INDEX IF NOT EXISTS ux_employee_event_manager
ON employee_event_booth_roles(employee_id, event_id)
WHERE booth_id IS NULL;

-- jestli je role null, tak ji automaticky doplní
-- u insert/update kontroluje: 
--   - jestli je event stejný tady i booth a booth existuje (pokud booth_id není null)
--   - jestli se booths.booth_type a role shodují (pokud role není null)
--   - zajistí, že pokud je employee pro event event_manager, tak nemůže být přirazen k specifickému stánku
--   - zajistí, že zde nemůže být přiřazen admin
CREATE OR REPLACE FUNCTION employee_event_booth_roles_limit_autocomplete_insert_update()
RETURNS trigger AS $$
DECLARE
  booth_event_id uuid;
  booths_type text;
  emp_is_admin boolean;
  found_row int;
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    IF NEW.role IS NULL AND NEW.booth_id IS NULL THEN
      NEW.role := 'event_manager';
    END IF;

    SELECT is_admin INTO emp_is_admin
    FROM employees
    WHERE id = NEW.employee_id
      AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'employee % does not exist or is deleted', NEW.employee_id;
    END IF;

    IF emp_is_admin THEN
      RAISE EXCEPTION 'admins cannot be assigned to employee_event_booth_roles (employee %)', NEW.employee_id;
    END IF;

    IF NEW.booth_id IS NOT NULL THEN
      SELECT event_id, booth_type INTO booth_event_id, booths_type
      FROM booths
      WHERE NEW.booth_id = id
      AND deleted_at IS NULL;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'booth % does not exist or is deleted', NEW.booth_id;
      END IF;

      IF NEW.role IS NULL THEN
        NEW.role := booths_type;
      END IF;

      IF booth_event_id IS DISTINCT FROM NEW.event_id THEN
        RAISE EXCEPTION 'booths event_id % and event_id % do not match', booth_event_id, NEW.event_id;
      END IF;

      IF booths_type IS DISTINCT FROM NEW.role THEN
        RAISE EXCEPTION 'booth_type % and role % do not match', booths_type, NEW.role;
      END IF;

      IF TG_OP = 'INSERT' THEN
        SELECT 1 INTO found_row
        FROM employee_event_booth_roles
        WHERE employee_id = NEW.employee_id
          AND event_id = NEW.event_id
          AND booth_id IS NULL
        LIMIT 1;
      ELSIF TG_OP = 'UPDATE' THEN
        SELECT 1 INTO found_row
        FROM employee_event_booth_roles
        WHERE employee_id = NEW.employee_id
          AND event_id = NEW.event_id
          AND booth_id IS NULL
          AND id IS DISTINCT FROM NEW.id
        LIMIT 1;
      END IF;

      IF FOUND THEN
        RAISE EXCEPTION 'employee % is already event_manager for event % and cannot be assigned to booths', NEW.employee_id, NEW.event_id;
      END IF;

    ELSIF NEW.booth_id IS NULL THEN
      IF NEW.role IS DISTINCT FROM 'event_manager' THEN
        RAISE EXCEPTION 'role must be event_manager when booth_id is NULL';
      END IF;

      IF TG_OP = 'INSERT' THEN
        SELECT 1 INTO found_row
        FROM employee_event_booth_roles
        WHERE employee_id = NEW.employee_id
          AND event_id = NEW.event_id
          AND booth_id IS NOT NULL
        LIMIT 1;
      ELSIF TG_OP = 'UPDATE' THEN
        SELECT 1 INTO found_row
        FROM employee_event_booth_roles
        WHERE employee_id = NEW.employee_id
          AND event_id = NEW.event_id
          AND booth_id IS NOT NULL
          AND id IS DISTINCT FROM NEW.id
        LIMIT 1;
      END IF;

      IF FOUND THEN
        RAISE EXCEPTION 'cannot assign event_manager for employee % on event % while they are assigned to booths', NEW.employee_id, NEW.event_id;
      END IF;

    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_employee_event_booth_roles_limit_autocomplete_insert_update
  BEFORE INSERT OR UPDATE ON employee_event_booth_roles
  FOR EACH ROW
  EXECUTE FUNCTION employee_event_booth_roles_limit_autocomplete_insert_update();



-- nic, co by se nemělo mazat se sem neodkazuje
-- ======================== product_event_prices ========================
CREATE TABLE IF NOT EXISTS product_event_prices (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id    uuid NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  event_id      uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  price         int NOT NULL CHECK (price > 0),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (product_id, event_id)
);
-- v této tabulce jsou delete i update povoleny



-- nic, co by se nemělo mazat se sem neodkazuje
-- ======================== event_product_booth_link ========================
CREATE TABLE IF NOT EXISTS event_product_booth_link (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_product_id  uuid NOT NULL REFERENCES product_event_prices(id) ON DELETE CASCADE,
  event_id          uuid NOT NULL REFERENCES events(id) ON DELETE CASCADE,
  booth_id          uuid NOT NULL REFERENCES booths(id) ON DELETE CASCADE,
  created_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_product_id, booth_id)
);
-- v této tabulce jsou delete i update povoleny

-- automaticky doplní event_id (z product_event_prices) a zkontroluje jestli se shoduje s booth_id
-- zkontroluje, že booth existuje
-- kontroluje že booth je seller
CREATE OR REPLACE FUNCTION event_product_booth_link_limit_autocomplete_update_insert()
RETURNS trigger AS $$
DECLARE
  booth_event_id uuid;
  event_product_price_event_id uuid;
BEGIN
  IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
    SELECT event_id INTO booth_event_id
      FROM booths
      WHERE NEW.booth_id = id
      AND booth_type = 'seller'
      AND deleted_at IS NULL;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'booth % does not exist, is not a seller or is deleted', NEW.booth_id;
    END IF;

    SELECT event_id INTO event_product_price_event_id
      FROM product_event_prices
      WHERE NEW.event_product_id = id;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'product_event_prices % does not exist', NEW.event_product_id;
    END IF;

    IF booth_event_id IS DISTINCT FROM event_product_price_event_id THEN
      RAISE EXCEPTION 'booths event_id % and product_event_prices event_id % do not match', booth_event_id, event_product_price_event_id;
    END IF;

    NEW.event_id := event_product_price_event_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_event_product_booth_link_limit_autocomplete_update_insert
  BEFORE INSERT OR UPDATE ON event_product_booth_link
  FOR EACH ROW
  EXECUTE FUNCTION event_product_booth_link_limit_autocomplete_update_insert();



-- -- ======================== tags ========================
-- CREATE TABLE IF NOT EXISTS tags (
--   id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
--   is_being_used   boolean NOT NULL
-- );



-- ======================== wallets ========================
-- created by?
CREATE TABLE IF NOT EXISTS wallets (
  id                            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- tag_id                        uuid REFERENCES tags(id) ON DELETE SET NULL,
  tag_id                        uuid,
  owner_id                      uuid REFERENCES users(id) ON DELETE SET NULL,
  balance_czk                   int NOT NULL DEFAULT 0, -- cache, není zdroj pravdy
  accountless_owner_identifier  text, -- nejspíš celé jméno, pro vrácení peněz na konci akce
  created_by                    uuid REFERENCES employees(id) NOT NULL,
  created_at                    timestamptz NOT NULL DEFAULT now(),
  deleted_at                    timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_tag_id_active ON wallets (tag_id) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS unique_index_owner_id_active ON wallets (owner_id) WHERE deleted_at IS NULL;

-- blokuje delete a změnu created_at a znovu nastavení deleted_at na null
CREATE OR REPLACE FUNCTION wallets_block_delete_limit_update()
RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'UPDATE' THEN
    IF (NEW.created_at IS DISTINCT FROM OLD.created_at) THEN
      RAISE EXCEPTION 'created_at is immutable and cannot be changed';
    END IF;
    IF (OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS DISTINCT FROM OLD.deleted_at) THEN
      RAISE EXCEPTION 'can not change deleted_at after deletion';
    END IF;

  ELSIF TG_OP = 'DELETE' THEN -- Soft-delete
    IF OLD.deleted_at IS NULL THEN
      UPDATE wallets
      SET deleted_at = now()
      WHERE id = OLD.id AND deleted_at IS NULL;
      RETURN NULL; -- zastav DELETE
    ELSE
      RETURN NULL;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_wallets_block_delete_limit_update
  BEFORE UPDATE OR DELETE ON wallets
  FOR EACH ROW
  EXECUTE FUNCTION wallets_block_delete_limit_update();



-- ======================== transactions ========================
-- zdroj pravdy pro wallets, nedá se měnit
CREATE TABLE IF NOT EXISTS transactions (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  -- tag_id            uuid NOT NULL REFERENCES tags(id) ON DELETE RESTRICT,
  tag_id            uuid NOT NULL,
  wallet_id         uuid NOT NULL REFERENCES wallets(id) ON DELETE RESTRICT,
  user_id           uuid REFERENCES users(id) ON DELETE RESTRICT,
  event_id          uuid NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
  booth_id          uuid NOT NULL REFERENCES booths(id) ON DELETE RESTRICT,
  transaction_type  text NOT NULL CHECK (transaction_type IN ('payment', 'refund', 'deposit', 'withdrawal')),
  amount_czk        int NOT NULL , -- kladné -> peníze přidány na wallet, záporné -> peníze odebrány z wallet
  balance_before    int NOT NULL, -- dělá trigger
  balance_after     int NOT NULL, -- dělá trigger
  occurred_at       timestamptz NOT NULL DEFAULT now(),
  performed_by      uuid NOT NULL REFERENCES employees(id) ON DELETE RESTRICT,
  products_info     jsonb DEFAULT '{}'::jsonb -- id (nezapomeň, že product mohl být smazán/upraven), price, name, amount
  -- metadata          jsonb DEFAULT '{}'::jsonb, -- keep?, info about product?
  CHECK (
    (transaction_type IN ('deposit', 'refund') AND amount_czk > 0)
    OR (transaction_type IN ('payment','withdrawal') AND amount_czk < 0)
  ),
  CHECK (balance_after = balance_before + amount_czk)
);
-- add the refund stuff

-- blokuje delete a update
-- u insert kontroluje: 
--  - že event je aktivní
--  - že booth existuje
--  - že booth event_id a event_id jsou shodné
--  - user existuje (pokud není null)
--  - jestli employee existuje a má dostatečnou roli
--  - jestli transaction_type je shodné s amount_czk
--  - jestli wallet existuje
--  - wallet.tag_id a wallet.user_id patří k transaction
--  - změna: jestli wallet má dost peněz. Na: Je povoleno, ale api by mělo zabránit
-- počítá a zapisuje balance_before a balance_after
-- updatuje wallet balance_czk
CREATE OR REPLACE FUNCTION transactions_block_delete_update_limit_insert()
RETURNS trigger AS $$
DECLARE
  bal_before int;
  bal_after int;
  employee_booth_role text;
  employee_is_admin boolean;
  booth_event_id uuid;
  wallet_tag_id uuid;
  wallet_owner_id uuid;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    RAISE EXCEPTION 'Updates are not allowed on table transactions';
  ELSIF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'Deletes are not allowed on table transactions';

  ELSIF TG_OP = 'INSERT' THEN
    -- event je aktivní
    PERFORM 1
      FROM events
      WHERE id = NEW.event_id
      AND start_at IS NOT NULL
      AND start_at <= NEW.occurred_at
      AND (end_at IS NULL OR NEW.occurred_at < end_at);

    IF NOT FOUND THEN
      RAISE EXCEPTION 'event % is not active', NEW.event_id;
    END IF;

    -- booth existuje, event_id = booths.event_id:
    SELECT event_id INTO booth_event_id
      FROM booths
      WHERE id = NEW.booth_id
      AND deleted_at IS NULL;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'booth % does not exist or is deleted', NEW.booth_id;
      END IF;

      IF booth_event_id IS DISTINCT FROM NEW.event_id THEN
        RAISE EXCEPTION 'booths event_id % and event_id % do not match', booth_event_id, NEW.event_id;
      END IF;

    -- user existuje:
    IF NEW.user_id IS NOT NULL THEN
      PERFORM 1
        FROM users
        WHERE id = NEW.user_id
        AND deleted_at IS NULL;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'user % does not exist or is deleted', NEW.user_id;
      END IF;
    END IF;

    -- employee existuje:
    SELECT is_admin INTO employee_is_admin
      FROM employees
      WHERE id = NEW.performed_by
      AND deleted_at IS NULL;
    
    IF NOT FOUND THEN
      RAISE EXCEPTION 'employee % does not exist or is deleted', NEW.performed_by;
    END IF;

    -- employee má dostatečnou roli:
    SELECT role INTO employee_booth_role
      FROM employee_event_booth_roles
      WHERE employee_id = NEW.performed_by
      AND event_id = NEW.event_id
      AND (booth_id = NEW.booth_id OR booth_id IS NULL)
      ORDER BY (booth_id IS NOT NULL) DESC
      LIMIT 1;
    
    IF NOT FOUND AND NOT employee_is_admin THEN
      RAISE EXCEPTION 'employee % does not have any role in the booth', NEW.performed_by;
    END IF;

    IF NEW.transaction_type IN ('deposit', 'withdrawal')
      AND NOT (employee_booth_role IN ('cashier', 'event_manager') OR employee_is_admin) THEN
        RAISE EXCEPTION 'employee with role % does not have necessary role to perform %', employee_booth_role, NEW.transaction_type;
    END IF;
    IF NEW.transaction_type IN ('payment', 'refund')
      AND NOT (employee_booth_role IN ('seller', 'cashier', 'event_manager') OR employee_is_admin) THEN
        RAISE EXCEPTION 'employee with role % does not have necessary role to perform %', employee_booth_role, NEW.transaction_type;
    END IF;

    -- transaction_type je shodné s amount_czk
    IF NEW.transaction_type in ('deposit', 'refund') AND NEW.amount_czk <= 0 THEN
      RAISE EXCEPTION '% amount must be > 0', NEW.transaction_type;
    ELSIF (NEW.transaction_type IN ('payment', 'withdrawal')) AND NEW.amount_czk >= 0 THEN
      RAISE EXCEPTION '% amount must be < 0', NEW.transaction_type;
    END IF;

    
    -- wallet existuje, získej potřebné data a zamkni řadu
    SELECT tag_id, owner_id, balance_czk INTO wallet_tag_id, wallet_owner_id, bal_before
      FROM wallets
      WHERE id = NEW.wallet_id
      AND deleted_at IS NULL
      FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'wallet % does not exist or is deleted', NEW.wallet_id;
    END IF;

    -- wallet.tag_id a wallet.user_id patří k transaction
    IF wallet_tag_id IS DISTINCT FROM NEW.tag_id THEN
      RAISE EXCEPTION 'wallet tag_id % does not match transaction tag_id %', wallet_tag_id, NEW.tag_id;
    END IF;

    IF wallet_owner_id IS DISTINCT FROM NEW.user_id THEN
      RAISE EXCEPTION 'wallet owner_id % does not match transaction user_id %', wallet_owner_id, NEW.user_id;
    END IF;

    -- spočítá balance_before
    bal_after := bal_before + NEW.amount_czk;

    -- -- wallet má dost peněz
    -- IF bal_after < 0 THEN
    --   RAISE EXCEPTION 'insufficient balance in wallet % (would be %)', NEW.wallet_id, bal_after;
    -- END IF;

    -- zapisuje balance_before a balance_after
    NEW.balance_before := bal_before;
    NEW.balance_after  := bal_after;
    -- updatuje wallet balance_czk
    UPDATE wallets SET balance_czk = bal_after WHERE id = NEW.wallet_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_transactions_block_delete_update_limit_insert
  BEFORE UPDATE OR DELETE OR INSERT ON transactions
  FOR EACH ROW
  EXECUTE FUNCTION transactions_block_delete_update_limit_insert();



-- -- update these:

-- development values
-- make sure to delete this !!!
-- employees, users, products, product_images, events, booths,
-- employee_event_booth_roles, product_event_prices,
-- event_product_booth_link, wallets, transactions

INSERT INTO employees (id, username, email, password_hash, is_admin, created_by, deleted_at)
VALUES 
('10000000000000000000000000000001', 'development_admin', 'email_admin@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', TRUE, NULL, NULL),
('10000000000000000000000000000002', 'development_event_manager', 'email_event_manager@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000003', 'development_cashier', 'email_cashier@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000004', 'development_seller', 'email_seller@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', FALSE, '10000000000000000000000000000001', NULL),
('10000000000000000000000000000005', 'development_admin_deleted', 'email_admin_deleted@gmail.com', '$argon2id$v=19$m=65536,t=3,p=2$HaqrwxL5kzBuWb6s+GVqKg$PmUeF6KsUupww8J9JT/Wpea73/wqqvpMAxnF/z7hFxo', TRUE, NULL, '2025-10-16 20:58:08.485849+0');

INSERT INTO products (id, name, description)
VALUES
('20000000000000000000000000000001', 'Hamburger 1', 'This is a yummy hamburger'),
('20000000000000000000000000000002', 'This is another hamburger but it has a considerably longer name. Like seriously what is this?', 'This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger This is a yummy hamburger '),
('20000000000000000000000000000003', 'Tall hamburger', 'This is a tall hamburger');

INSERT INTO product_images (product_id, image_path, filename, content_type, size_bytes, width, height, alt_text)
VALUES
('20000000000000000000000000000001', '/static/uploads', 'hamburger1.png', 'image/png', 54289, 225, 225, 'Hamburger picture'),
('20000000000000000000000000000002', '/static/uploads', 'hamburger2.png', 'image/png', 1882222, 1500, 1125, 'Delicious hamburger picture'),
('20000000000000000000000000000003', '/static/uploads', 'hamburger3.png', 'image/png', 5308416, 1440, 2465, 'Tall delicious hamburger picture');

INSERT INTO events (id, name, start_at, end_at, created_by)
VALUES
('30000000000000000000000000000001', 'development_event', '2025-10-16 20:40:55+02', '2026-10-16 20:40:55+02', '10000000000000000000000000000001'),
('30000000000000000000000000000002', 'development_event2', '2025-10-16 20:40:55+02', '2026-10-16 20:40:55+02', '10000000000000000000000000000001'),
('30000000000000000000000000000003', 'development_event3', '2025-12-16 20:40:55+02', '2026-12-16 20:40:55+02', '10000000000000000000000000000001');

INSERT INTO booths (id, name, event_id, booth_type, created_by)
VALUES
('40000000000000000000000000000001', 'development_booth_cashier', '30000000000000000000000000000001', 'cashier', '10000000000000000000000000000001'),
('40000000000000000000000000000002', 'development_booth_seller', '30000000000000000000000000000001', 'seller', '10000000000000000000000000000001'),
('40000000000000000000000000000003', 'development_booth_seller2', '30000000000000000000000000000001', 'seller', '10000000000000000000000000000001');

INSERT INTO employee_event_booth_roles (id, employee_id, event_id, booth_id)
VALUES
('50000000000000000000000000000003', '10000000000000000000000000000002', '30000000000000000000000000000001', NULL),
('50000000000000000000000000000001', '10000000000000000000000000000003', '30000000000000000000000000000001', '40000000000000000000000000000001'),
('50000000000000000000000000000002', '10000000000000000000000000000004', '30000000000000000000000000000001', '40000000000000000000000000000002');

INSERT INTO product_event_prices (id, product_id, event_id, price)
VALUES
('60000000000000000000000000000001', '20000000000000000000000000000001', '30000000000000000000000000000001', 2000),
('60000000000000000000000000000002', '20000000000000000000000000000002', '30000000000000000000000000000001', 145),
('60000000000000000000000000000003', '20000000000000000000000000000003', '30000000000000000000000000000001', 95);

INSERT INTO event_product_booth_link (id, event_product_id, booth_id)
VALUES
('70000000000000000000000000000001', '60000000000000000000000000000001', '40000000000000000000000000000002'),
('70000000000000000000000000000002', '60000000000000000000000000000002', '40000000000000000000000000000002'),
('70000000000000000000000000000003', '60000000000000000000000000000003', '40000000000000000000000000000002'),
('70000000000000000000000000000004', '60000000000000000000000000000001', '40000000000000000000000000000003');

INSERT INTO wallets (id, tag_id, balance_czk, created_by)
VALUES
('80000000000000000000000000000001', '90000000000000000000000000000001', 5340, '10000000000000000000000000000003'),
('80000000000000000000000000000002', '90000000000000000000000000000002', 21, '10000000000000000000000000000003');



-- maybe?
-- maybe add indexes for frequently queried columns:
-- CREATE INDEX ix_transactions_tag_occurred_at ON transactions (tag_id, occurred_at DESC);
-- CREATE INDEX ix_transactions_account_occurred_at ON transactions (account_id, occurred_at DESC);
-- transactions (performed_by, occurred_at DESC)
-- consider event_id indexes.
