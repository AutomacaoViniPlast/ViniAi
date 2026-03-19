import { supabase } from "./supabase";

export const signUp = async (email: string, password: string, nome: string) => {
  const { data, error } = await supabase.auth.signUp({
    email,
    password,
    options: {
      data: { nome } // passa o nome nos metadados
    }
  });
  if (error) throw error;
  return data;
};

export const signIn = async (email: string, password: string) => {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw error;
  return data;
};

export const resetPassword = async (email: string) => {
  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: `${window.location.origin}/nova-senha`,
  });
  if (error) throw error;
};

export const signOut = async () => {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
};

export const getUser = async () => {
  const { data } = await supabase.auth.getUser();
  return data.user;
};